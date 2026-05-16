#!/usr/bin/env python3.12
"""
run-slack-dispatch-router: Slack DMポーリング→エージェントディスパッチ

目的:
    Slack DM（D09M7MYRCVD）の未処理投稿をポーリングし、LLM判定で
    適切なエージェント/パイプラインを選定、別プロセスで非同期起動する。
    スレッドIDとセッションIDのマッピングを管理し、既存セッションがあれば
    継続、なければ新規起動する。

使い方:
    python3.12 scripts/run-slack-dispatch-router.py

出力: JSON（処理結果サマリー）
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"

# Slack設定
DM_CHANNEL = "D09M7MYRCVD"
TARGET_USER = "U076LRL1B35"
FETCH_LIMIT = 10

# ファイルパス
WORK_DIR = HOME / "Documents" / "works" / "slack_dispatch"
SESSION_MAP_FILE = WORK_DIR / "session-map.json"
PROCESSED_FILE = WORK_DIR / "processed-messages.json"
LOG_DIR = WORK_DIR / "logs"
LOG_FILE = LOG_DIR / "dispatch.log"

# エージェント定義ディレクトリ
KIRO_AGENTS_DIR = HOME / ".kiro" / "agents"
CLAUDE_AGENTS_DIR = HOME / ".claude" / "agents"

# LLM判定用
DISPATCH_AGENT = "slack-dispatch-router"

# タイムアウト・リトライ
REQUEST_TIMEOUT = 30
MAX_LOG_LINES = 500


# ─── ユーティリティ ──────────────────────────────────────────────

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def log(message: str) -> None:
    """ログ出力（stderr + ログファイル）。"""
    timestamp = now_jst()
    line = f"[{timestamp}] {message}"
    print(line, file=sys.stderr)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def rotate_log(log_file: Path, max_lines: int, keep_lines: int = 200) -> None:
    """ログファイルが max_lines を超えていたら末尾 keep_lines 行に切り詰める。"""
    if not log_file.exists():
        return
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > max_lines:
        log_file.write_text(
            "\n".join(lines[-keep_lines:]) + "\n", encoding="utf-8"
        )


def load_env() -> None:
    """環境変数をロードする（launchd環境対応）。"""
    if os.environ.get("MY_SLACK_OAUTH_TOKEN"):
        return
    result = subprocess.run(
        [str(PLATFORM_CMD), "source-env"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ[key] = value


# ─── JSON管理 ────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    """JSONファイルを読み込む。存在しなければ空dictを返す。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: Path, data: dict) -> None:
    """JSONファイルに書き込む。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def prune_old_entries(data: dict, max_entries: int = 200) -> dict:
    """古いエントリを削除して最大件数に制限する。

    processed_at または started_at でソートし、古い順に削除する。
    """
    if len(data) <= max_entries:
        return data

    # ソートキー: processed_at > started_at > キー自体
    def sort_key(item: tuple) -> str:
        _, v = item
        if isinstance(v, dict):
            return v.get("processed_at", v.get("started_at", ""))
        return ""

    sorted_items = sorted(data.items(), key=sort_key)
    # 新しい方からmax_entries件を残す
    keep = dict(sorted_items[-max_entries:])
    return keep


# ─── Slack API ───────────────────────────────────────────────────

def slack_api(method: str, params: dict | None = None,
              body: dict | None = None) -> dict | None:
    """Slack Web APIを呼び出す。

    Args:
        method: APIメソッド名（例: conversations.history）
        params: GETパラメータ
        body: POSTボディ（指定時はPOST）

    Returns:
        APIレスポンスのdict。失敗時はNone。
    """
    token = os.environ.get("MY_SLACK_OAUTH_TOKEN", "")
    if not token:
        log("❌ MY_SLACK_OAUTH_TOKEN が未設定")
        return None

    url = f"https://slack.com/api/{method}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    if body:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
    else:
        req = urllib.request.Request(url)

    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if not result.get("ok"):
            log(f"⚠️  Slack API error ({method}): {result.get('error')}")
            return None
        return result
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        log(f"❌ Slack API request failed ({method}): {e}")
        return None


def fetch_messages() -> list[dict]:
    """DM チャンネルから最新メッセージを取得し、対象ユーザーの投稿を返す。"""
    result = slack_api("conversations.history", {
        "channel": DM_CHANNEL,
        "limit": str(FETCH_LIMIT),
    })
    if not result:
        return []

    messages = result.get("messages", [])
    # 対象ユーザーの投稿のみ抽出（bot_messageやsubtypeありは除外）
    return [
        msg for msg in messages
        if msg.get("user") == TARGET_USER
        and not msg.get("subtype")
    ]


def reply_to_thread(thread_ts: str, text: str) -> bool:
    """元スレッドに返信する。"""
    result = slack_api("chat.postMessage", body={
        "channel": DM_CHANNEL,
        "thread_ts": thread_ts,
        "text": text,
    })
    if result:
        log(f"  💬 返信送信成功: {text[:50]}")
    else:
        log(f"  ⚠️  返信送信失敗: {text[:50]}")
    return result is not None


# ─── エージェント一覧取得 ────────────────────────────────────────

def scan_agents() -> list[dict]:
    """利用可能なエージェント一覧を取得する。

    AI_COMMAND_TYPE に応じて .kiro/agents/ または .claude/agents/ をスキャンする。

    Returns:
        [{"name": "...", "description": "..."}, ...] のリスト
    """
    ai_type = os.environ.get("AI_COMMAND_TYPE", "claude")
    agents: list[dict] = []

    if ai_type == "kiro-cli":
        # .kiro/agents/*.json をスキャン
        if KIRO_AGENTS_DIR.exists():
            for f in sorted(KIRO_AGENTS_DIR.glob("*.json")):
                if f.name.startswith("agent_config"):
                    continue
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    name = data.get("name", f.stem)
                    desc = data.get("description", "")
                    agents.append({"name": name, "description": desc})
                except (json.JSONDecodeError, OSError):
                    continue
    else:
        # .claude/agents/*.md をスキャン（ファイル名がエージェント名）
        if CLAUDE_AGENTS_DIR.exists():
            for f in sorted(CLAUDE_AGENTS_DIR.glob("*.md")):
                name = f.stem
                # 先頭行からdescriptionを抽出
                try:
                    first_lines = f.read_text(encoding="utf-8").split("\n")[:5]
                    desc = ""
                    for line in first_lines:
                        if line.startswith("# "):
                            desc = line[2:].strip()
                            break
                    agents.append({"name": name, "description": desc})
                except OSError:
                    agents.append({"name": name, "description": ""})

    return agents


# ─── LLM判定 ─────────────────────────────────────────────────────

def determine_agent(message_text: str, agents: list[dict]) -> str | None:
    """LLM判定で投稿内容から起動すべきエージェント名を決定する。

    Args:
        message_text: Slack投稿のテキスト
        agents: 利用可能なエージェント一覧

    Returns:
        エージェント名。判定不能時はNone。
    """
    agent_list = "\n".join(
        f"- {a['name']}: {a['description']}" for a in agents
    )

    prompt = (
        f"以下のSlack投稿内容に最も適したエージェントを1つ選んでください。\n"
        f"エージェント名のみを返してください（説明不要）。\n"
        f"該当するエージェントがない場合は「none」と返してください。\n\n"
        f"## 利用可能なエージェント一覧\n{agent_list}\n\n"
        f"## Slack投稿内容\n{message_text}\n\n"
        f"回答（エージェント名のみ）:"
    )

    ai_type = os.environ.get("AI_COMMAND_TYPE", "claude")
    if ai_type == "kiro-cli":
        cmd = [
            "kiro-cli", "chat", "--trust-all-tools", "--no-interactive",
            "--agent", DISPATCH_AGENT, prompt,
        ]
    else:
        cmd = [
            "claude", "--print", "--dangerously-skip-permissions",
            "--agent", DISPATCH_AGENT, prompt,
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log(f"⚠️  LLM判定失敗: exit={result.returncode}")
            return None

        output = result.stdout.strip()

        # claude --output-format json の場合はJSONパース
        if ai_type != "kiro-cli" and output.startswith("{"):
            try:
                data = json.loads(output)
                output = data.get("result", "").strip()
            except json.JSONDecodeError:
                pass

        # エージェント名を抽出（余分なテキストを除去）
        # 改行があれば最初の行のみ
        output = output.split("\n")[0].strip()
        # バッククォートや引用符を除去
        output = output.strip("`\"'")

        if output.lower() == "none" or not output:
            return None

        # 有効なエージェント名か確認
        valid_names = {a["name"] for a in agents}
        if output in valid_names:
            return output

        # 部分一致を試みる
        for name in valid_names:
            if name in output or output in name:
                return name

        log(f"⚠️  LLM判定結果が不正: '{output}'")
        return None

    except subprocess.TimeoutExpired:
        log("⚠️  LLM判定タイムアウト")
        return None
    except OSError as e:
        log(f"❌ LLM判定コマンド実行失敗: {e}")
        return None


# ─── エージェント起動 ─────────────────────────────────────────────

def launch_agent(
    agent_name: str,
    prompt: str,
    thread_ts: str,
    session_id: str | None = None,
) -> tuple[int, str | None, str]:
    """エージェントをラッパースクリプト経由で非同期起動する。

    ラッパーはエージェント完了後にレポートを元スレッドに返信する。

    Args:
        agent_name: 起動するエージェント名
        prompt: プロンプト（投稿内容）
        thread_ts: 元スレッドのタイムスタンプ
        session_id: 既存セッションID（あれば再開）

    Returns:
        (pid, new_session_id, marker_ts) のタプル。
        marker_ts はログマーカーのタイムスタンプ（セッションID回収時の照合用）。
        起動失敗時は (0, None, "")。
    """
    # エージェント実行ログ
    agent_log = LOG_DIR / f"{agent_name}.log"

    try:
        marker_ts = now_jst()
        with open(agent_log, "a", encoding="utf-8") as f:
            f.write(f"\n--- [{marker_ts}] dispatch: {prompt[:100]}... ---\n")

        # ラッパースクリプト経由で起動
        # ラッパーがエージェント実行 → 完了後にSlack通知を行う
        wrapper_cmd = [
            "python3.12", str(SCRIPTS_DIR / "dispatch-agent-wrapper.py"),
            "--agent", agent_name,
            "--thread-ts", thread_ts,
            "--channel", DM_CHANNEL,
            "--log-file", str(agent_log),
        ]
        if session_id:
            wrapper_cmd.extend(["--session-id", session_id])
        wrapper_cmd.extend(["--", prompt])

        proc = subprocess.Popen(
            wrapper_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        pid = proc.pid

        # セッションID: ラッパーは同期実行するので、完了後にログから回収
        if session_id:
            return pid, session_id, marker_ts

        # 新規セッション: kiro-cliの場合のみ即時取得を試みる
        ai_type = os.environ.get("AI_COMMAND_TYPE", "claude")
        if ai_type == "kiro-cli":
            new_session_id = _get_latest_kiro_session_id()
        else:
            new_session_id = None
        return pid, new_session_id, marker_ts

    except OSError as e:
        log(f"❌ エージェント起動失敗 ({agent_name}): {e}")
        return 0, None, ""


def _get_latest_kiro_session_id() -> str | None:
    """kiro-cliの最新セッションIDを取得する。"""
    time.sleep(2)
    try:
        result = subprocess.run(
            ["kiro-cli", "chat", "--list-sessions"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            match = re.search(
                r"Chat SessionId:\s*([0-9a-f-]{36})", line
            )
            if match:
                return match.group(1)
        return None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _recover_session_ids() -> None:
    """前回起動分でセッションIDが未取得のエントリをログから回収する。

    ログファイルには複数回の実行結果が蓄積されるため、
    session_map の started_at 以降に書き込まれたJSON出力のみを対象にする。
    """
    session_map = load_json(SESSION_MAP_FILE)
    updated = False

    for thread_ts, entry in session_map.items():
        if entry.get("session_id"):
            continue  # 既に取得済み

        agent_name = entry.get("agent", "")
        if not agent_name:
            continue

        started_at = entry.get("started_at", "")
        if not started_at:
            continue

        agent_log = LOG_DIR / f"{agent_name}.log"
        if not agent_log.exists():
            continue

        # ログファイルから該当実行のセクションを特定し、session_idを探す
        try:
            content = agent_log.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            # started_at に対応する dispatch マーカーを探す
            # マーカー形式: --- [{timestamp}] dispatch: ... ---
            marker_idx = -1
            for i, line in enumerate(lines):
                if f"[{started_at}]" in line and "dispatch:" in line:
                    marker_idx = i
                    break

            if marker_idx == -1:
                continue

            # マーカー以降の行からJSON出力を探す
            # 次のマーカーが出現するまでの範囲に限定
            end_idx = len(lines)
            for i in range(marker_idx + 1, len(lines)):
                if "--- [" in lines[i] and "dispatch:" in lines[i]:
                    end_idx = i
                    break

            for line in reversed(lines[marker_idx + 1:end_idx]):
                line = line.strip()
                if line.startswith("{") and '"session_id"' in line:
                    try:
                        data = json.loads(line)
                        sid = data.get("session_id")
                        if sid:
                            entry["session_id"] = sid
                            updated = True
                            log(f"  🔑 セッションID回収: {agent_name} → {sid}")
                            break
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    if updated:
        save_json(SESSION_MAP_FILE, session_map)


# ─── メイン処理 ──────────────────────────────────────────────────

def main() -> None:
    """メインエントリポイント。"""
    # ディレクトリ準備
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ログローテーション
    rotate_log(LOG_FILE, MAX_LOG_LINES)

    # 環境変数ロード
    load_env()

    log("🚀 slack-dispatch-router 起動")

    # 前回起動分のセッションID回収（claude mode）
    _recover_session_ids()

    # Slackメッセージ取得
    messages = fetch_messages()
    if not messages:
        log("📭 未処理メッセージなし（取得0件）")
        print(json.dumps({"success": True, "processed": 0}, ensure_ascii=False))
        return

    log(f"📬 {len(messages)}件のメッセージ取得")

    # 処理済みJSON読み込み
    processed = load_json(PROCESSED_FILE)
    session_map = load_json(SESSION_MAP_FILE)

    # 未処理メッセージをフィルタ
    unprocessed = [
        msg for msg in messages
        if msg.get("ts") and msg["ts"] not in processed
    ]

    if not unprocessed:
        log("✅ 全メッセージ処理済み")
        print(json.dumps({"success": True, "processed": 0}, ensure_ascii=False))
        return

    log(f"🔍 未処理: {len(unprocessed)}件")

    # エージェント一覧取得
    agents = scan_agents()
    if not agents:
        log("❌ 利用可能なエージェントが見つかりません")
        print(json.dumps(
            {"success": False, "error": "no agents found"},
            ensure_ascii=False,
        ))
        sys.exit(1)

    log(f"📋 利用可能エージェント: {len(agents)}件")

    # 各未処理メッセージを処理
    dispatched = 0
    errors = 0

    for msg in unprocessed:
        ts = msg["ts"]
        text = msg.get("text", "")
        thread_ts = msg.get("thread_ts", ts)  # スレッド内ならthread_ts、なければts

        log(f"  📝 処理中: ts={ts}, text={text[:50]}...")

        # 処理開始マーク
        processed[ts] = {
            "processed_at": now_jst(),
            "status": "processing",
            "text_preview": text[:100],
        }
        save_json(PROCESSED_FILE, processed)

        # LLM判定
        agent_name = determine_agent(text, agents)
        if not agent_name:
            log(f"  ⏭️  判定不能（スキップ）: {text[:50]}")
            processed[ts]["status"] = "skipped"
            processed[ts]["reason"] = "no_matching_agent"
            save_json(PROCESSED_FILE, processed)
            reply_to_thread(thread_ts, "⚠️ 該当するエージェントが見つかりませんでした。")
            continue

        log(f"  🎯 判定結果: {agent_name}")

        # セッションID検索
        existing_session = session_map.get(thread_ts)
        session_id: str | None = None
        if existing_session and existing_session.get("session_id"):
            session_id = existing_session["session_id"]
            log(f"  🔄 既存セッション再開: {session_id}")

        # エージェント起動
        pid, new_session_id, marker_ts = launch_agent(
            agent_name, text, thread_ts, session_id,
        )

        if pid == 0:
            log(f"  ❌ 起動失敗: {agent_name}")
            processed[ts]["status"] = "error"
            processed[ts]["error"] = "launch_failed"
            save_json(PROCESSED_FILE, processed)
            reply_to_thread(thread_ts, f"❌ エージェント `{agent_name}` の起動に失敗しました。")
            errors += 1
            continue

        # セッションマップ更新
        if new_session_id:
            session_map[thread_ts] = {
                "agent": agent_name,
                "session_id": new_session_id,
                "started_at": marker_ts,
                "last_used_at": marker_ts,
            }
        elif existing_session:
            session_map[thread_ts]["last_used_at"] = now_jst()
        else:
            # 新規起動だがセッションID未取得（後で_recover_session_idsで回収）
            session_map[thread_ts] = {
                "agent": agent_name,
                "session_id": None,
                "started_at": marker_ts,
                "last_used_at": marker_ts,
            }

        save_json(SESSION_MAP_FILE, session_map)

        # 処理済み更新
        processed[ts]["status"] = "dispatched"
        processed[ts]["agent"] = agent_name
        processed[ts]["session_id"] = new_session_id or session_id
        processed[ts]["pid"] = pid
        save_json(PROCESSED_FILE, processed)

        # Slack返信
        if session_id:
            reply_to_thread(
                thread_ts,
                f"🔄 `{agent_name}` セッション再開しました（PID={pid}）",
            )
        else:
            reply_to_thread(
                thread_ts,
                f"🚀 `{agent_name}` を起動しました（PID={pid}）",
            )

        dispatched += 1

    # 結果サマリー
    log(f"📊 完了: dispatched={dispatched}, errors={errors}")

    # 古いエントリの削除（肥大化防止）
    processed = prune_old_entries(processed)
    save_json(PROCESSED_FILE, processed)
    session_map = prune_old_entries(session_map)
    save_json(SESSION_MAP_FILE, session_map)

    print(json.dumps({
        "success": errors == 0,
        "processed": dispatched + errors,
        "dispatched": dispatched,
        "errors": errors,
    }, ensure_ascii=False))


# ─── エントリポイント ────────────────────────────────────────────

from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
