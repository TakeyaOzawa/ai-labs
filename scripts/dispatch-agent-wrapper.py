#!/usr/bin/env python3.12
"""
dispatch-agent-wrapper: ディスパッチされたエージェントを実行し、完了後にSlack通知する

目的:
    run-slack-dispatch-router.py から起動され、エージェントを実行した後、
    出力レポートを元のSlackスレッドに返信として投稿する。

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

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
NOTIFY_SCRIPT = SCRIPTS_DIR / "notify-slack.py"

# レポートファイル検出パターン（claude JSON出力の result フィールドから）
# 例: "出力: `Documents/works/scout_reports/.../file.md`"
#      "保存先: `Documents/works/research_materials/2026-05-16_ollama.md`"
REPORT_PATH_PATTERNS = [
    re.compile(r"(?:出力|保存先|レポート|ファイル)[：:]?\s*`?([~/]?Documents/works/[^\s`\"]+\.md)`?"),
    re.compile(r"(?:出力|保存先|レポート|ファイル)[：:]?\s*`?(\S+/works/[^\s`\"]+\.md)`?"),
]


# ─── ユーティリティ ──────────────────────────────────────────────

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


def extract_report_path(log_content: str) -> Path | None:
    """ログ内容からレポートファイルパスを抽出する。

    claude --output-format json の場合、result フィールドにパスが含まれる。
    kiro-cli の場合、標準出力にパスが含まれる。
    """
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
    path = _find_path_in_text(log_content, home)
    return path


def _find_path_in_text(text: str, home: Path) -> Path | None:
    """テキストからレポートファイルパスを抽出する。"""
    for pattern in REPORT_PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            path_str = match.group(1)
            # ~/... や Documents/... を絶対パスに変換
            if path_str.startswith("~/"):
                path = Path(path_str).expanduser()
            elif path_str.startswith("Documents/"):
                path = home / path_str
            else:
                path = Path(path_str)
            if path.exists():
                return path
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
        description="ディスパッチエージェントラッパー"
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

    # AI コマンド構築
    ai_type = os.environ.get("AI_COMMAND_TYPE", "claude")

    if ai_type == "kiro-cli":
        cmd = ["kiro-cli", "chat", "--trust-all-tools", "--no-interactive"]
        if args.session_id:
            cmd.extend(["--resume-id", args.session_id])
        else:
            cmd.extend(["--agent", args.agent])
        cmd.append(args.prompt)
    else:
        if args.session_id:
            cmd = [
                "claude", "--print", "--dangerously-skip-permissions",
                "--output-format", "json",
                "--resume", args.session_id, args.prompt,
            ]
        else:
            cmd = [
                "claude", "--print", "--dangerously-skip-permissions",
                "--output-format", "json",
                "--agent", args.agent, args.prompt,
            ]

    # エージェント実行（同期: 完了を待つ）
    # 実行前のログファイル行数を記録（自分が書いた部分のみ解析するため）
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

    # 今回実行分のログのみ抽出（行数ベースで安全にスライス）
    all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    log_content = "\n".join(all_lines[pre_lines:])
    report_path = extract_report_path(log_content)

    if report_path:
        # レポートファイルを元スレッドに投稿
        notify_slack_thread(report_path, args.channel, args.thread_ts, log_file)
    else:
        # レポートファイルが見つからない場合、結果テキストを投稿
        # claude JSON出力からresultを抽出
        result_text = _extract_result_text(log_content)
        if result_text:
            # 長すぎる場合は切り詰め
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

from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
