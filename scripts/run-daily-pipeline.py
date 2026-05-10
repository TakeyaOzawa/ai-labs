#!/usr/bin/env python3.12
"""
run-daily-pipeline: 日次scoutパイプラインをkiro-cliで実行する（タスク管理付き）

目的:
    日次scoutパイプラインの全エージェントを順次実行し、
    RSSフィード取得→各scout実行→結果サマリー出力を一括で行う。
    タスクファイルベース進捗管理を行う。

使い方:
    python3.12 scripts/run-daily-pipeline.py [基準日]
    python3.12 scripts/run-daily-pipeline.py 2026-05-07
    python3.12 scripts/run-daily-pipeline.py --no-task-file

出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
依存: kiro-cli, python3.12 (fetch-rss-feeds.py)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
LOG_DIR = HOME / "logs"
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"

AGENTS = [
    "tech-trend-scout",
    "biz-car-trend-scout",
    "academic-trend-scout",
    "gws-trend-scout",
    "slack-trend-scout",
    "github-org-trend-scout",
    "github-public-trend-scout",
    "notion-trend-scout",
]

NOTIFY_FILE_MAP: dict[str, str] = {
    "tech-trend-scout": "scout_histories/tech_trends/daily/{date}_tech_trends.md",
    "biz-car-trend-scout": "scout_histories/biz_car_trends/daily/{date}_biz_car_trends.md",
    "academic-trend-scout": "scout_histories/academic_trends/daily/{date}_academic_trends.md",
    "gws-trend-scout": "scout_histories/gws_trends/daily/{date}_gws_daily.md",
    "slack-trend-scout": "scout_histories/slack_trends/daily/{date}_slack_daily.md",
    "github-org-trend-scout": "scout_histories/github_org_trends/daily/{date}_github-org_daily.md",
    "github-public-trend-scout": "scout_histories/github_public_trends/daily/{date}_github-public_daily.md",
    "notion-trend-scout": "scout_histories/notion_trends/daily/{date}_notion_daily.md",
}

MAX_LOG_LINES = 1000
MAX_AGENT_LOG_LINES = 500


# ─── ユーティリティ ──────────────────────────────────────────────

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def rotate_log(log_file: Path, max_lines: int, keep_lines: int = 200) -> None:
    """ログファイルが max_lines を超えていたら末尾 keep_lines 行に切り詰める。"""
    if not log_file.exists():
        return
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > max_lines:
        log_file.write_text("\n".join(lines[-keep_lines:]) + "\n", encoding="utf-8")


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


def run_kiro_cli(prompt: str, log_file: Path) -> bool:
    """kiro-cliを実行し、成功/失敗を返す。"""
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(
            ["kiro-cli", "chat", "--trust-all-tools", "--no-interactive", prompt],
            stdout=f, stderr=subprocess.STDOUT,
        )
    return result.returncode == 0


def log_error(pipeline: str, agent: str, message: str) -> None:
    """error.logに親タスク > 子タスクの2階層ヘッダー付きでエラーを記録する。"""
    timestamp = now_jst()
    print(f"[{timestamp}] [{pipeline}] > [{agent}] {message}", file=sys.stderr)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    # オプション解析
    use_task_file = True
    positional_args: list[str] = []

    for arg in sys.argv[1:]:
        if arg == "--no-task-file":
            use_task_file = False
        else:
            positional_args.append(arg)

    # 基準日
    if positional_args:
        base_date = positional_args[0]
    else:
        yesterday = datetime.now(tz=JST) - timedelta(days=1)
        base_date = yesterday.strftime("%Y-%m-%d")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # スリープ防止
    caffeinate_pid = start_caffeinate()

    # 環境変数ロード
    load_env()

    # 収集フェーズ用の環境変数設定
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("SLACK_REFERENCE_BOT_TOKEN", "")
    os.environ["SLACK_TEAM_ID"] = os.environ.get("SLACK_REFERENCE_TEAM_ID", "")

    # ログローテーション
    log_file = LOG_DIR / "scout-daily-pipeline.log"
    rotate_log(log_file, MAX_LOG_LINES)

    # error.log ローテーション（launchd StandardErrorPath）
    error_log = LOG_DIR / "scout-daily-pipeline-error.log"
    rotate_log(error_log, MAX_LOG_LINES)

    print(f"[{now_jst()}] 📋 日次scoutパイプライン起動（基準日: {base_date}）")

    # ─── Step 0: タスクファイル生成 ───────────────────────────────
    task_file: Path | None = None
    if use_task_file:
        print(f"[{now_jst()}] Step 0: タスクファイル生成...")
        task_file = create_task_file(base_date)
        if task_file:
            print(f"[{now_jst()}]    タスクファイル: {task_file}")
            update_task(task_file, scope="parent",
                        updates={"status": "running", "started_at": now_jst()})
        else:
            print(f"[{now_jst()}] ⚠️  タスクファイル生成失敗。進捗管理なしで続行。")
            use_task_file = False

    # ─── Step 1: RSSフィード事前取得 ──────────────────────────────
    print(f"[{now_jst()}] Step 1: RSSフィード事前取得...")
    rss_script = SCRIPTS_DIR / "fetch-rss-feeds.py"
    if rss_script.exists():
        for category in ["tech", "biz", "academic"]:
            result = subprocess.run(
                ["python3.12", str(rss_script), "--category", category, "--date", base_date],
                capture_output=True, text=True,
            )
            status = "✅" if result.returncode == 0 else "⚠️ "
            print(f"   {status} {category}")
    else:
        print("   ⚠️  RSSスクリプト未検出（スキップ）")

    # ─── Step 2: 各scoutエージェントを順次実行 ───────────────────
    print(f"[{now_jst()}] Step 2: scoutエージェント実行開始...")

    success = 0
    failed = 0
    failed_names: list[str] = []

    for agent in AGENTS:
        agent_start = now_jst()
        print(f"[{agent_start}] 🔄 {agent} 実行中...")

        agent_log = LOG_DIR / f"scout-daily-{agent}.log"
        rotate_log(agent_log, MAX_AGENT_LOG_LINES, keep_lines=100)

        # タスクファイル: running に更新
        child_task_id = ""
        if use_task_file and task_file:
            child_task_id = get_child_task_id(task_file, agent)
            if child_task_id:
                update_task(task_file, task_id=child_task_id,
                            updates={"status": "running", "started_at": agent_start})
                update_task(task_file, scope="parent",
                            updates={"status_detail": f"{agent} 実行中"})

        # エージェント実行
        prompt = (
            f"{agent} エージェントとして動作してください。"
            f" ~/.shared-ai/prompts/{agent}.md をreadFileで読み込み、"
            f"そこに記載されたワークフローに従って実行してください。"
            f"基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )

        if run_kiro_cli(prompt, agent_log):
            agent_end = now_jst()
            print(f"[{agent_end}]    ✅ {agent} 完了")
            success += 1
            if use_task_file and child_task_id:
                update_task(task_file, task_id=child_task_id,
                            updates={"status": "completed", "completed_at": agent_end})
        else:
            agent_end = now_jst()
            print(f"[{agent_end}]    ❌ {agent} 失敗（ログ: {agent_log}）")
            log_error("daily-pipeline", agent, "kiro-cli exit non-zero")
            failed += 1
            failed_names.append(agent)
            if use_task_file and child_task_id:
                update_task(task_file, task_id=child_task_id,
                            updates={"status": "failed", "error": "kiro-cli exit non-zero",
                                     "completed_at": agent_end})

    # ─── Step 3: 親タスク完了処理 ────────────────────────────────
    end_now = now_jst()
    total = success + failed

    if use_task_file and task_file:
        if failed > 0:
            update_task(task_file, scope="parent", updates={
                "status": "failed", "completed_at": end_now,
                "status_detail": f"{failed}件失敗: {' '.join(failed_names)}",
                "error": f"{failed}/{total} tasks failed",
            })
        else:
            update_task(task_file, scope="parent", updates={
                "status": "completed", "completed_at": end_now,
                "status_detail": "全子タスク完了",
            })

    # ─── Step 4: Slack通知 ───────────────────────────────────────
    notify_now = now_jst()
    print(f"[{notify_now}] Step 4: Slack通知...")

    # 通知用に環境変数を切り替え
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("MY_SLACK_OAUTH_TOKEN", "")

    notify_success = 0
    notify_skipped = 0
    notify_log = LOG_DIR / "scout-daily-slack-notify.log"
    rotate_log(notify_log, MAX_AGENT_LOG_LINES, keep_lines=100)

    for agent in AGENTS:
        template = NOTIFY_FILE_MAP.get(agent, "")
        if not template:
            notify_skipped += 1
            continue

        file_path = HOME / "Documents" / "works" / template.format(date=base_date)
        if not file_path.exists():
            print(f"   ⏭️  {agent}: 出力ファイルなし（スキップ）")
            notify_skipped += 1
            continue

        print(f"[{now_jst()}]    📨 {agent} 通知中...")
        notify_prompt = (
            f"slack-notifier エージェントとして動作してください。"
            f" ~/.shared-ai/prompts/slack-notifier.md をreadFileで読み込み、"
            f"そこに記載されたワークフローに従って実行してください。"
            f" file_path={file_path}"
        )

        if run_kiro_cli(notify_prompt, notify_log):
            print(f"[{now_jst()}]    ✅ {agent} 通知完了")
            notify_success += 1
        else:
            print(f"[{now_jst()}]    ⚠️  {agent} 通知失敗（レポート作成は成功扱い）")
            log_error("daily-pipeline", f"slack-notify:{agent}", "通知失敗")

    notify_end = now_jst()
    print(f"[{notify_end}] 📨 通知完了: ✅{notify_success}件 / ⏭️{notify_skipped}件スキップ")

    # ─── Step 5: 完了サマリー ────────────────────────────────────
    print(f"[{notify_end}] 📊 実行完了: ✅{success}件 / ❌{failed}件 (全{total}件)")
    if failed > 0:
        print(f"[{notify_end}]    失敗: {' '.join(failed_names)}")
    if use_task_file and task_file:
        print(f"[{notify_end}]    タスクファイル: {task_file}")
    print(f"[{notify_end}] ✅ 日次scoutパイプライン完了（基準日: {base_date}）")

    # スリープ防止解除
    stop_caffeinate(caffeinate_pid)


# ─── ヘルパー関数 ────────────────────────────────────────────────

def start_caffeinate() -> str:
    """スリープ防止を開始し、プロセスIDを返す。"""
    pid = str(os.getpid())
    result = subprocess.run(
        [str(PLATFORM_CMD), "caffeinate-start", pid],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def stop_caffeinate(cafe_pid: str) -> None:
    """スリープ防止を停止する。"""
    if cafe_pid and cafe_pid != "0":
        subprocess.run(
            [str(PLATFORM_CMD), "caffeinate-stop", cafe_pid],
            capture_output=True, text=True,
        )


def create_task_file(base_date: str) -> Path | None:
    """タスクファイルを生成し、パスを返す。"""
    result = subprocess.run(
        ["python3.12", str(SCRIPTS_DIR / "create-daily-tasks.py"), base_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    # 出力からファイルパスを抽出
    for line in result.stdout.splitlines():
        if "ファイル:" in line:
            path_str = line.split("ファイル:")[1].strip()
            path = Path(path_str)
            if path.exists():
                return path
    return None


def get_child_task_id(task_file: Path, task_name: str) -> str:
    """タスクファイルから指定タスク名のIDを取得する。"""
    with open(task_file, encoding="utf-8") as f:
        data = json.load(f)
    for child in data.get("child_tasks", []):
        if child.get("task_name") == task_name:
            return child.get("task_id", "")
    return ""


def update_task(task_file: Path, task_id: str = "", scope: str = "child",
                updates: dict | None = None) -> None:
    """タスクを更新する。"""
    if updates is None:
        return

    cmd = [
        "python3.12", str(SCRIPTS_DIR / "update-task.py"),
        "--task-file", str(task_file),
        "--scope", scope if scope == "parent" else "child",
        "--set", json.dumps(updates, ensure_ascii=False),
    ]
    if scope != "parent" and task_id:
        cmd.extend(["--task-id", task_id])

    subprocess.run(cmd, capture_output=True, text=True)



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
