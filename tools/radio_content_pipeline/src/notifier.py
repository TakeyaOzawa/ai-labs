#!/usr/bin/env python3.12
"""
notifier: Slack通知モジュール

目的:
    パイプラインの各イベント（録音完了、文字起こし完了、エラー、日次サマリー）を
    Slack Webhookで通知する。fire-and-forget方式で呼び出し元をブロックしない。

使い方:
    python3.12 src/notifier.py --test
    python3.12 src/notifier.py --daily-summary

出力: Slack通知送信
依存: なし（標準ライブラリのみ、urllib使用）
"""
import argparse
import json
import os
import sys
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_manager import (
    RECORDING_TASKS_FILE,
    TRANSCRIPTION_TASKS_FILE,
    get_status_summary,
)

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
REQUEST_TIMEOUT = 10


# ─── Slack送信 ───────────────────────────────────────────────────

def _send_slack(message: str) -> bool:
    """Slack Webhookにメッセージを送信する。

    Args:
        message: 送信するテキスト

    Returns:
        送信成功時True
    """
    if not SLACK_WEBHOOK_URL:
        print("[notifier] SLACK_WEBHOOK_URL not set, skipping")
        return False

    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        print(f"[notifier] Slack send failed: {e}", file=sys.stderr)
        return False


def _send_slack_async(message: str) -> None:
    """Slack通知を非同期（別スレッド）で送信する。fire-and-forget。"""
    thread = threading.Thread(target=_send_slack, args=(message,), daemon=True)
    thread.start()


# ─── 通知テンプレート ────────────────────────────────────────────

def notify_recording_complete(
    program_name: str,
    file_path: str,
    elapsed_seconds: float,
) -> None:
    """録音完了通知を送信する。"""
    message = (
        f"📻 録音完了: *{program_name}*\n"
        f"ファイル: `{Path(file_path).name}`\n"
        f"処理時間: {elapsed_seconds:.0f}秒"
    )
    _send_slack_async(message)


def notify_transcription_complete(
    program_name: str,
    file_path: str,
    char_count: int,
    processing_seconds: float,
    duration_seconds: float,
) -> None:
    """文字起こし完了通知を送信する。"""
    rtf = processing_seconds / duration_seconds if duration_seconds > 0 else 0
    message = (
        f"📝 文字起こし完了: *{program_name}*\n"
        f"ファイル: `{Path(file_path).name}`\n"
        f"文字数: {char_count:,}文字\n"
        f"処理時間: {processing_seconds:.0f}秒 "
        f"(音声: {duration_seconds:.0f}秒, RTF: {rtf:.2f}x)"
    )
    _send_slack_async(message)


def notify_summary_complete(
    program_name: str,
    summary_path: str,
    summary_preview: str,
) -> None:
    """要約完了通知を送信する。"""
    preview = summary_preview[:200] + "..." if len(summary_preview) > 200 else summary_preview
    message = (
        f"📋 要約完了: *{program_name}*\n"
        f"ファイル: `{Path(summary_path).name}`\n"
        f"---\n{preview}"
    )
    _send_slack_async(message)


def notify_error(
    program_name: str,
    stage: str,
    error_message: str,
) -> None:
    """エラー通知を送信する。"""
    message = (
        f"❌ エラー発生: *{program_name}*\n"
        f"ステージ: {stage}\n"
        f"エラー: ```{error_message[:500]}```"
    )
    _send_slack_async(message)


def notify_daily_summary() -> None:
    """日次サマリー通知を送信する。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")

    rec_summary = get_status_summary(RECORDING_TASKS_FILE)
    trans_summary = get_status_summary(TRANSCRIPTION_TASKS_FILE)

    # ディスク使用量チェック
    disk_info = _get_disk_usage()

    rec_total = rec_summary["total"]
    rec_success = rec_summary["success"]
    rec_failed = rec_summary["failed"]

    trans_total = trans_summary["total"]
    trans_success = trans_summary["success"]
    trans_failed = trans_summary["failed"]

    rec_icon = "✅" if rec_failed == 0 and rec_total > 0 else "⚠️"
    trans_icon = "✅" if trans_failed == 0 and trans_total > 0 else "⚠️"

    message = (
        f"📻 ラジオパイプライン日次レポート ({today})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{rec_icon} 録音: {rec_success}/{rec_total}件完了"
    )
    if rec_failed > 0:
        message += f" ({rec_failed}件失敗)"
    message += (
        f"\n{trans_icon} 文字起こし: {trans_success}/{trans_total}件完了"
    )
    if trans_failed > 0:
        message += f" ({trans_failed}件失敗)"

    if disk_info:
        message += (
            f"\n💾 ディスク使用量: "
            f"{disk_info['used_gb']:.1f}GB / {disk_info['total_gb']:.1f}GB "
            f"({disk_info['percent']}%)"
        )
        if disk_info["percent"] >= 80:
            message += " ⚠️ 容量逼迫"

    _send_slack(message)
    print(f"[notifier] Daily summary sent for {today}")


def _get_disk_usage() -> dict | None:
    """/dataのディスク使用量を取得する。"""
    try:
        import shutil
        usage = shutil.disk_usage("/data")
        return {
            "total_gb": usage.total / (1024 ** 3),
            "used_gb": usage.used / (1024 ** 3),
            "free_gb": usage.free / (1024 ** 3),
            "percent": int(usage.used / usage.total * 100),
        }
    except (OSError, FileNotFoundError):
        return None


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="Slack通知 — パイプラインイベント通知"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="テスト通知を送信",
    )
    parser.add_argument(
        "--daily-summary", action="store_true",
        help="日次サマリーを送信",
    )
    args = parser.parse_args()

    if args.test:
        success = _send_slack("🔔 テスト通知: パイプライン通知システム正常動作")
        result = {"success": success}
        print(json.dumps(result, ensure_ascii=False))
    elif args.daily_summary:
        notify_daily_summary()
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
