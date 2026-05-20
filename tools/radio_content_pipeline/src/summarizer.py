#!/usr/bin/env python3.12
"""
summarizer: LLM要約モジュール（invoke-agent.py経由）

目的:
    文字起こし完了後に、invoke-agent.pyを使って
    radio-transcript-summarizerエージェントを別プロセスで起動し、
    要約完了後にslack-notifyエージェントで通知する。

使い方:
    python3.12 src/summarizer.py --file /data/transcripts/TBS_番組名_20260518.json
    python3.12 src/summarizer.py --file /data/transcripts/TBS_番組名_20260518.json --name "空気階段の踊り場"
    python3.12 src/summarizer.py --file /data/transcripts/TBS_番組名_20260518.json --no-notify

出力: 要約Markdownファイル（/data/summaries/）+ Slack通知
依存: なし（invoke-agent.pyを別プロセスで呼び出す）
"""
import argparse
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

SUMMARIES_DIR = Path(os.environ.get("SUMMARIES_DIR", "/data/summaries"))
INVOKE_AGENT = Path.home() / "scripts" / "ai" / "invoke-agent.py"
PYTHON = "python3.12"

# Slack通知設定
SLACK_CHANNEL = os.environ.get("SLACK_NOTIFY_CHANNEL", "")
SLACK_THREAD_TS = os.environ.get("SLACK_NOTIFY_THREAD_TS", "")


# ─── invoke-agent.py呼び出し ─────────────────────────────────────

def _invoke_agent(
    agent_name: str,
    prompt: str,
    input_path: str = "",
    output_path: str = "",
    no_slack: bool = False,
    slack_channel: str = "",
    slack_thread_ts: str = "",
    timeout: int = 900,
) -> subprocess.CompletedProcess:
    """invoke-agent.pyを別プロセスで実行する。

    Args:
        agent_name: エージェント名
        prompt: プロンプトテキスト
        input_path: 入力ファイルパス
        output_path: 出力ファイルパス
        no_slack: Slack通知を無効化
        slack_channel: Slack通知先チャンネルID
        slack_thread_ts: Slack通知先スレッドTS
        timeout: タイムアウト秒

    Returns:
        subprocess.CompletedProcess
    """
    cmd = [
        PYTHON, str(INVOKE_AGENT),
        "--agent", agent_name,
        "--prompt", prompt,
        "--timeout", str(timeout),
    ]

    if input_path:
        cmd.extend(["--input-path", input_path])
    if output_path:
        cmd.extend(["--output-path", output_path])
    if no_slack:
        cmd.append("--no-slack")
    if slack_channel:
        cmd.extend(["--slack-channel", slack_channel])
    if slack_thread_ts:
        cmd.extend(["--slack-thread-ts", slack_thread_ts])

    print(f"[summarizer] Invoking: {agent_name}")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout + 60,  # invoke-agent自体のタイムアウトより少し長く
    )


# ─── 要約実行 ────────────────────────────────────────────────────

def summarize_with_agent(
    transcript_path: str,
    program_name: str,
) -> bool:
    """radio-transcript-summarizerエージェントで要約を実行する。

    Args:
        transcript_path: 文字起こしJSONファイルのパス
        program_name: 番組名

    Returns:
        成功時True
    """
    # 出力先パスを決定
    stem = Path(transcript_path).stem
    output_path = str(SUMMARIES_DIR / f"{stem}_summary.md")

    prompt = (
        f"{transcript_path} を要約してください。"
        f"番組名は「{program_name}」です。"
    )

    result = _invoke_agent(
        agent_name="radio-transcript-summarizer",
        prompt=prompt,
        input_path=transcript_path,
        output_path=output_path,
        no_slack=True,  # 要約完了通知は別途slack-notifyで送る
        timeout=900,
    )

    if result.returncode == 0:
        print(f"[summarizer] Complete: {program_name} → {output_path}")
        return True
    else:
        print(
            f"[summarizer] Failed: {program_name} — {result.stderr[:500]}",
            file=sys.stderr,
        )
        return False


def notify_summary_complete(
    program_name: str,
    summary_path: str,
) -> None:
    """要約完了をslack-notifyエージェントで通知する。

    Args:
        program_name: 番組名
        summary_path: 要約ファイルパス
    """
    prompt = (
        f"📋 要約完了: *{program_name}*\n"
        f"ファイル: `{Path(summary_path).name}`\n"
        f"上記のファイルの内容を読み込んで、要約のハイライト（3行程度）と共に"
        f"Slackに投稿してください。"
    )

    slack_channel = SLACK_CHANNEL
    slack_thread_ts = SLACK_THREAD_TS

    result = _invoke_agent(
        agent_name="slack-notify",
        prompt=prompt,
        input_path=summary_path,
        slack_channel=slack_channel,
        slack_thread_ts=slack_thread_ts,
        timeout=120,
    )

    if result.returncode == 0:
        print(f"[summarizer] Slack notification sent: {program_name}")
    else:
        print(
            f"[summarizer] Slack notification failed: {result.stderr[:200]}",
            file=sys.stderr,
        )


# ─── 非同期実行（transcriber.pyから呼ばれる） ────────────────────

def summarize_async(
    program_name: str,
    full_text: str,
    audio_filename: str,
) -> None:
    """要約を非同期（別スレッド）で実行する。fire-and-forget。

    Docker環境内ではinvoke-agent.pyにアクセスできないため、
    ホスト側のinvoke-agent.pyが存在する場合のみ実行する。
    Docker内から呼ばれた場合はスキップし、ログに記録する。

    Args:
        program_name: 番組名
        full_text: 文字起こし全文（未使用、互換性のため残す）
        audio_filename: 元の音声ファイル名
    """
    if not INVOKE_AGENT.exists():
        print(
            f"[summarizer] invoke-agent.py not found at {INVOKE_AGENT}, "
            f"skipping (run manually from host: "
            f"python3.12 src/summarizer.py --file /data/transcripts/"
            f"{Path(audio_filename).stem}.json)"
        )
        return

    # 音声ファイル名からtranscript JSONパスを推定
    stem = Path(audio_filename).stem
    transcript_path = f"/data/transcripts/{stem}.json"

    if not Path(transcript_path).exists():
        print(f"[summarizer] Transcript not found: {transcript_path}")
        return

    def _run():
        try:
            success = summarize_with_agent(transcript_path, program_name)
            if success:
                summary_path = str(SUMMARIES_DIR / f"{stem}_summary.md")
                notify_summary_complete(program_name, summary_path)
        except Exception as e:
            print(f"[summarizer] Error: {e}", file=sys.stderr)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="LLM要約 — invoke-agent.py経由でradio-transcript-summarizerを実行"
    )
    parser.add_argument(
        "--file",
        help="文字起こしJSONファイルパス",
    )
    parser.add_argument(
        "--name",
        default="",
        help="番組名（省略時: ファイル名から推定）",
    )
    parser.add_argument(
        "--no-notify", action="store_true",
        help="Slack通知を無効化",
    )
    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(2)

    json_path = Path(args.file)
    if not json_path.exists():
        print(f"File not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    # 番組名の推定
    if args.name:
        program_name = args.name
    else:
        parts = json_path.stem.split("_")
        program_name = "_".join(parts[1:-1]) if len(parts) >= 3 else json_path.stem

    # 要約実行
    success = summarize_with_agent(str(json_path), program_name)

    if success and not args.no_notify:
        stem = json_path.stem
        summary_path = str(SUMMARIES_DIR / f"{stem}_summary.md")
        notify_summary_complete(program_name, summary_path)

    result = {"success": success, "program_name": program_name}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
