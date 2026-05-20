#!/usr/bin/env python3.12
"""
main: メインプロセス（スケジューラ + オーケストレーション）

目的:
    毎朝6時に番組検索→録音タスク追記を実行する。
    録音ワーカー・文字起こしワーカーは別コンテナで独立稼働し、
    タスクリスト（JSONファイル）を介して連携する。

使い方:
    python3.12 src/main.py
    python3.12 src/main.py --run-now
    python3.12 src/main.py --schedule "0 6 * * *"

出力: タスクリスト更新
依存: pyyaml, apscheduler
"""
import argparse
import json
import os
import signal
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from task_manager import (
    RECORDING_TASKS_FILE,
    TRANSCRIPTION_TASKS_FILE,
    STATE_DIR,
    add_task,
    check_timeouts,
    create_task,
    get_status_summary,
)
from program_resolver import resolve_programs
from notifier import notify_daily_summary, notify_error

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/app/config"))
PROGRAMS_CONFIG = CONFIG_DIR / "programs.yml"
PIPELINE_CONFIG = CONFIG_DIR / "pipeline.yml"

RECORDINGS_DIR = Path(os.environ.get("RECORDINGS_DIR", "/data/recordings"))
DEFAULT_CRON = os.environ.get("SCHEDULE_CRON", "0 6 * * *")

_shutdown_requested = False


def _signal_handler(signum, frame):
    """SIGTERMハンドラ: グレースフルシャットダウン。"""
    global _shutdown_requested
    _shutdown_requested = True
    print("[main] Shutdown requested...")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ─── 設定読み込み ────────────────────────────────────────────────

def load_pipeline_config() -> dict:
    """pipeline.ymlを読み込む。

    Returns:
        パイプライン設定dict
    """
    if not PIPELINE_CONFIG.exists():
        return {}
    content = PIPELINE_CONFIG.read_text(encoding="utf-8")
    return yaml.safe_load(content) or {}


# ─── メイン処理: 番組検索→タスク追記 ─────────────────────────────

def run_program_discovery() -> dict:
    """番組検索を実行し、録音タスクを追記する。

    Returns:
        実行結果dict
    """
    print("[main] Starting program discovery...")

    # タイムアウトチェック（前回のprocessingが残っている場合）
    config = load_pipeline_config()
    timeout_hours = (
        config.get("recording", {}).get("timeout_hours", 6)
    )
    timed_out = check_timeouts(RECORDING_TASKS_FILE, timeout_hours)
    if timed_out:
        print(f"[main] {len(timed_out)} recording task(s) timed out")

    trans_timeout = (
        config.get("transcription", {}).get("timeout_hours", 6)
    )
    trans_timed_out = check_timeouts(TRANSCRIPTION_TASKS_FILE, trans_timeout)
    if trans_timed_out:
        print(
            f"[main] {len(trans_timed_out)} transcription task(s) timed out"
        )

    # 番組検索
    try:
        programs = resolve_programs(PROGRAMS_CONFIG)
    except Exception as e:
        error_msg = f"Program discovery failed: {e}"
        print(f"[main] {error_msg}", file=sys.stderr)
        notify_error("パイプライン", "program_discovery", error_msg)
        return {"success": False, "error": error_msg}

    # タスク追記
    added_count = 0
    skipped_count = 0

    for prog in programs:
        output_path = str(RECORDINGS_DIR / prog["output_filename"])
        task = create_task(
            file_path=output_path,
            program_name=prog["program_name"],
            station_id=prog["station_id"],
            source_url=prog["download_url"],
            metadata={
                "title": prog["title"],
                "start_time": prog["start_time"],
                "end_time": prog["end_time"],
                "performers": prog.get("performers", ""),
            },
        )
        if add_task(RECORDING_TASKS_FILE, task):
            added_count += 1
            print(
                f"[main] Added: {prog['program_name']} "
                f"({prog['station_id']} {prog['date']})"
            )
        else:
            skipped_count += 1

    result = {
        "success": True,
        "discovered": len(programs),
        "added": added_count,
        "skipped": skipped_count,
        "timestamp": datetime.now(JST).isoformat(),
    }
    print(
        f"[main] Discovery complete: "
        f"{len(programs)} found, {added_count} added, "
        f"{skipped_count} skipped"
    )
    return result


# ─── スケジューラ ────────────────────────────────────────────────

def run_scheduled():
    """スケジューラモード: cronスケジュールに従って定期実行する。"""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    config = load_pipeline_config()
    cron_expr = config.get("schedule", {}).get("cron", DEFAULT_CRON)

    print(f"[main] Scheduler started (cron: {cron_expr})")
    print(f"[main] Config: {PROGRAMS_CONFIG}")
    print(f"[main] State dir: {STATE_DIR}")
    print(
        "[main] Note: recorder/transcriber workers run in separate "
        "containers and monitor task lists independently"
    )

    # ディレクトリ初期化
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    scheduler = BlockingScheduler(timezone="Asia/Tokyo")

    def _scheduled_job():
        """スケジュール実行ジョブ。"""
        print(f"[main] Scheduled job triggered at {datetime.now(JST)}")
        run_program_discovery()

    # cron式をパース
    parts = cron_expr.split()
    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    scheduler.add_job(_scheduled_job, trigger)

    # 日次サマリー（毎日23:00に送信）
    scheduler.add_job(
        notify_daily_summary,
        CronTrigger(hour=23, minute=0),
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[main] Scheduler stopped")


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="パイプラインメインプロセス — スケジューラ + オーケストレーション"
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="即時実行（番組検索→タスク追記のみ。ワーカーは別コンテナ）",
    )
    parser.add_argument(
        "--discover-only", action="store_true",
        help="番組検索のみ実行（--run-nowと同義）",
    )
    parser.add_argument(
        "--schedule",
        metavar="CRON",
        help="スケジュール実行（cron式を指定）",
    )
    parser.add_argument(
        "--daily-summary", action="store_true",
        help="日次サマリーを送信",
    )
    args = parser.parse_args()

    # ディレクトリ初期化
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    if args.run_now or args.discover_only:
        result = run_program_discovery()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.daily_summary:
        notify_daily_summary()

    elif args.schedule:
        os.environ["SCHEDULE_CRON"] = args.schedule
        run_scheduled()

    else:
        # デフォルト: スケジューラモード
        run_scheduled()


if __name__ == "__main__":
    main()
