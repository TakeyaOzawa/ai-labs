#!/usr/bin/env python3.12
"""
dispatch-agent-wrapper: ディスパッチされたエージェントを実行し、完了後にSlack通知する

目的:
    run-slack-dispatch-router.py から起動され、エージェントを実行した後、
    出力レポートを元のSlackスレッドに返信として投稿する。
    StepParams.slack.enabled: false でエージェント自身の通知をスキップし、
    wrapper が元スレッドへ投稿する。

使い方:
    python3.12 scripts/dispatch-agent-wrapper.py \
        --agent <agent_name> \
        --thread-ts <thread_ts> \
        --channel <channel_id> \
        --log-file <log_path> \
        [--session-id <session_id>] \
        -- <prompt>

出力: エージェント実行ログ + Slack通知結果
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402

import argparse
import json
import os
import re
import subprocess


from models import (
    AgentExecutor,
    ExecutionContext,
    OutputParams,
    SlackParams,
    Step,
    StepParams,
)
from pipeline_engine import HOME, SCRIPTS_DIR, build_agent_prompt_with_params, now_jst
from config import load_env
from logger import PipelineLogger

# ─── 定数定義 ────────────────────────────────────────────────────

PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
NOTIFY_SCRIPT = SCRIPTS_DIR / "slack" / "notify-slack.py"

# レポートファイル検出パターン
# 高精度パターン（キーワード付き、最初のマッチを採用）
_KEYWORD_PATTERNS = [
    # キーワード直後にパスが続くパターン（「保存先: ~/Documents/...」等）
    re.compile(r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?`?((?:~/)?Documents/works/[^\s`\"\x1b]+\.md)`?"),
    re.compile(r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?`?(\S+/works/[^\s`\"\x1b]+\.md)`?"),
    # ANSIエスケープシーケンスを含む場合（kiro-cli出力）
    re.compile(r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]*?(?:\x1b\[[0-9;]*m)*`?((?:~/)?Documents/works/[^\s`\"\x1b]+\.md)`?"),
]
# フォールバックパターン（末尾から検索して最後のマッチを採用）
_FALLBACK_PATTERNS = [
    # kiro-cliのファイル作成/更新ログ形式（「Creating:/Updating:/Appending to: Documents/works/...」）
    re.compile(r"(?:Creating|Updating|Appending to):\s*(?:\x1b\[[0-9;]*m)*((?:~/|/[^\s`\"\x1b]*?)?Documents/works/[^\s`\"\x1b]+\.md)"),
    # パスが単独で出現するパターン（キーワードなし、バッククォート囲み）
    re.compile(r"`((?:~/)?Documents/works/(?!scout_reports/)(?!tmp/)[^\s`\"\x1b]+\.md)`"),
]
# 除外パス（フォールバックで誤検出を防ぐ）
_EXCLUDED_PATH_SEGMENTS = ("/tmp/", "/scout_reports/")


# ─── ユーティリティ ──────────────────────────────────────────────

def extract_report_path(log_content: str) -> Path | None:
    """ログ内容からレポートファイルパスを抽出する。"""
    home = Path.home()

    # JSON出力からresultフィールドを抽出
    for line in reversed(log_content.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"result"' in line:
            try:
                data = json.loads(line)
                result_text = data.get("result", "")
                path = _find_path_in_text(result_text, home)
                if path:
                    return path
            except json.JSONDecodeError:
                continue

    # JSON以外のテキスト出力からも探す
    return _find_path_in_text(log_content, home)


def _find_path_in_text(text: str, home: Path) -> Path | None:
    """テキストからレポートファイルパスを抽出する。"""
    # ANSIエスケープシーケンスを除去したテキストでもマッチを試みる
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    clean_text = ansi_escape.sub("", text)

    for search_text in [clean_text, text]:
        # キーワード付きパターン（高精度）を先に試す
        for pattern in _KEYWORD_PATTERNS:
            match = pattern.search(search_text)
            if match:
                path_str = match.group(1)
                path = _resolve_path(path_str, home)
                if path and path.exists():
                    return path

    # フォールバック: 末尾から検索して最後の有効なマッチを採用
    for search_text in [clean_text, text]:
        for pattern in _FALLBACK_PATTERNS:
            matches = list(pattern.finditer(search_text))
            if matches:
                for match in reversed(matches):
                    path_str = match.group(1)
                    # 除外パスセグメントを含む場合はスキップ
                    if any(seg in path_str for seg in _EXCLUDED_PATH_SEGMENTS):
                        continue
                    path = _resolve_path(path_str, home)
                    if path and path.exists():
                        return path
    return None


def _resolve_path(path_str: str, home: Path) -> Path | None:
    """パス文字列をPathオブジェクトに変換する。"""
    if path_str.startswith("~/"):
        return Path(path_str).expanduser()
    elif path_str.startswith("Documents/"):
        return home / path_str
    elif path_str.startswith("/"):
        return Path(path_str)
    return None


def notify_slack_thread(
    file_path: Path, channel: str, thread_ts: str, log_file: Path,
) -> bool:
    """レポートファイルを元スレッドに投稿する。"""
    cmd = [
        "python3.12", str(NOTIFY_SCRIPT),
        "--file", str(file_path),
        "--channel", channel,
        "--thread", thread_ts,
    ]
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return result.returncode == 0


def notify_slack_text(
    text: str, channel: str, thread_ts: str, log_file: Path,
) -> bool:
    """テキストメッセージを元スレッドに投稿する。"""
    cmd = [
        "python3.12", str(NOTIFY_SCRIPT),
        "--text", text,
        "--channel", channel,
        "--thread", thread_ts,
    ]
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return result.returncode == 0


# ─── メイン処理 ──────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ディスパッチエージェントラッパー（統一ステップモデル）"
    )
    parser.add_argument("--agent", required=True, help="エージェント名")
    parser.add_argument("--thread-ts", required=True, help="元スレッドのts")
    parser.add_argument("--channel", required=True, help="チャンネルID")
    parser.add_argument("--log-file", required=True, help="ログファイルパス")
    parser.add_argument("--session-id", default=None, help="既存セッションID")
    parser.add_argument("prompt", help="プロンプト（投稿内容）")
    args = parser.parse_args()

    log_file = Path(args.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 環境変数ロード
    load_env()

    # Step 構築（slack.enabled=False でエージェント自身の通知をスキップ）
    step = Step(
        name=args.agent,
        executor=AgentExecutor(agent_name=args.agent, prompt_text=args.prompt),
        timeout=600,
        params=StepParams(
            slack=SlackParams(enabled=False),
        ),
    )

    # agent_params YAMLブロック付きプロンプトを生成
    prompt_with_params = build_agent_prompt_with_params(step)

    # AI コマンド構築
    from importlib.util import module_from_spec, spec_from_file_location
    _spec = spec_from_file_location("ai_cli_utils", SCRIPTS_DIR / "ai" / "ai-cli-utils.py")
    _mod = module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    cmd = _mod.build_ai_command(
        prompt_with_params,
        agent_name=args.agent,
        session_id=args.session_id or "",
        output_format="json" if _mod.get_ai_type() == "claude" else "",
    )

    # エージェント実行（同期）
    pre_lines = 0
    if log_file.exists():
        pre_lines = len(
            log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        )

    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)

    # 実行結果に基づいてSlack通知
    if result.returncode != 0:
        notify_slack_text(
            f"❌ `{args.agent}` がエラーで終了しました（exit={result.returncode}）",
            args.channel, args.thread_ts, log_file,
        )
        sys.exit(1)

    # 今回実行分のログのみ抽出
    all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    log_content = "\n".join(all_lines[pre_lines:])
    report_path = extract_report_path(log_content)

    if report_path:
        notify_slack_thread(report_path, args.channel, args.thread_ts, log_file)
    else:
        result_text = _extract_result_text(log_content)
        if result_text:
            if len(result_text) > 3000:
                result_text = result_text[:3000] + "\n\n…（省略）"
            notify_slack_text(
                f"✅ `{args.agent}` 完了\n\n{result_text}",
                args.channel, args.thread_ts, log_file,
            )
        else:
            notify_slack_text(
                f"✅ `{args.agent}` 完了（レポートファイルなし）",
                args.channel, args.thread_ts, log_file,
            )


def _extract_result_text(log_content: str) -> str:
    """ログからエージェントの結果テキストを抽出する。"""
    for line in reversed(log_content.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"result"' in line:
            try:
                data = json.loads(line)
                return data.get("result", "")
            except json.JSONDecodeError:
                continue
    return ""


# ─── エントリポイント ────────────────────────────────────────────


if __name__ == "__main__":
    main()
