#!/usr/bin/env python3.12
"""
recorder: 録音ワーカー（サブプロセスA）

目的:
    タスクリストを監視し、yt-dlp-rajikoでradikoタイムフリー番組を
    並行ダウンロードする。完了後に文字起こしタスクを追記する。

使い方:
    python3.12 src/recorder.py
    python3.12 src/recorder.py --url "https://radiko.jp/#!/ts/TBS/20260519000000"
    python3.12 src/recorder.py --once

出力: ダウンロード済みM4Aファイル（/data/recordings/）
依存: yt-dlp, yt-dlp-rajiko
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_manager import (
    RECORDING_TASKS_FILE,
    TRANSCRIPTION_TASKS_FILE,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    STATUS_FAILED,
    add_task,
    check_timeouts,
    create_task,
    get_pending_tasks,
    update_status,
)

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

RECORDINGS_DIR = Path(os.environ.get("RECORDINGS_DIR", "/data/recordings"))
POLL_INTERVAL = int(os.environ.get("RECORDER_POLL_INTERVAL", "10"))
MAX_CONCURRENT = int(os.environ.get("RECORDER_MAX_CONCURRENT", "2"))
TIMEOUT_HOURS = float(os.environ.get("RECORDER_TIMEOUT_HOURS", "6"))
SOCKET_TIMEOUT = 15

# グレースフルシャットダウン用フラグ
_shutdown_requested = False


def _signal_handler(signum, frame):
    """SIGTERMハンドラ: グレースフルシャットダウンを要求する。"""
    global _shutdown_requested
    _shutdown_requested = True
    print("[recorder] Shutdown requested, finishing current tasks...")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ─── ダウンロード処理 ────────────────────────────────────────────

def download_program(
    source_url: str,
    output_dir: Path,
    output_filename: str | None = None,
) -> Path:
    """yt-dlp-rajikoで番組をダウンロードする。

    Args:
        source_url: radiko タイムフリーURL
        output_dir: 出力ディレクトリ
        output_filename: 出力ファイル名（Noneの場合yt-dlpのデフォルト）

    Returns:
        ダウンロードされたファイルのPath

    Raises:
        subprocess.CalledProcessError: yt-dlp実行失敗時
        FileNotFoundError: ダウンロード後にファイルが見つからない場合
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_filename:
        output_template = str(output_dir / output_filename)
        # 拡張子を除去（yt-dlpが自動付与）
        if output_template.endswith(".m4a"):
            output_template = output_template[:-4]
        output_template += ".%(ext)s"
    else:
        output_template = str(
            output_dir
            / "%(channel_id)s_%(title)s_%(upload_date)s.%(ext)s"
        )

    cmd = [
        "yt-dlp",
        "--socket-timeout", str(SOCKET_TIMEOUT),
        "--no-overwrites",
        "-o", output_template,
        source_url,
    ]

    print(f"[recorder] Downloading: {source_url}")
    print(f"[recorder] Output: {output_template}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_HOURS * 3600,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=error_msg
        )

    # ダウンロードされたファイルを特定
    # yt-dlpの出力から[download] Destination: を探す
    downloaded_file = None
    for line in (result.stdout + result.stderr).splitlines():
        if "[download] Destination:" in line:
            path_str = line.split("[download] Destination:", 1)[1].strip()
            downloaded_file = Path(path_str)
            break
        elif "[download]" in line and "has already been downloaded" in line:
            # 既にダウンロード済み
            path_str = line.split("[download]", 1)[1].strip()
            path_str = path_str.split(" has already")[0].strip()
            downloaded_file = Path(path_str)
            break

    # Mergerの出力も確認（FixupM4a等で最終ファイル名が変わる場合）
    for line in (result.stdout + result.stderr).splitlines():
        if "[Merger]" in line or "[FixupM4a]" in line:
            if "Merging formats into" in line:
                path_str = line.split("Merging formats into", 1)[1].strip()
                path_str = path_str.strip('"')
                downloaded_file = Path(path_str)

    if downloaded_file and downloaded_file.exists():
        return downloaded_file

    # フォールバック: output_dirから最新のm4aファイルを探す
    m4a_files = sorted(output_dir.glob("*.m4a"), key=lambda f: f.stat().st_mtime)
    if m4a_files:
        return m4a_files[-1]

    raise FileNotFoundError(
        f"Downloaded file not found. yt-dlp output:\n{result.stdout}"
    )


# ─── タスク処理 ──────────────────────────────────────────────────

def process_recording_task(task: dict) -> dict:
    """1件の録音タスクを処理する。

    Args:
        task: タスクエントリ

    Returns:
        処理結果dict
    """
    file_path = task["file_path"]
    source_url = task["source_url"]
    program_name = task["program_name"]

    # ステータスをprocessingに更新
    update_status(RECORDING_TASKS_FILE, file_path, STATUS_PROCESSING)

    try:
        start_time = time.time()
        downloaded = download_program(
            source_url=source_url,
            output_dir=RECORDINGS_DIR,
            output_filename=Path(file_path).name,
        )
        elapsed = time.time() - start_time

        # ステータスをsuccessに更新
        update_status(RECORDING_TASKS_FILE, file_path, STATUS_SUCCESS)

        # 文字起こしタスクを追記
        transcription_task = create_task(
            file_path=str(downloaded),
            program_name=program_name,
            station_id=task["station_id"],
            metadata=task.get("metadata", {}),
        )
        add_task(TRANSCRIPTION_TASKS_FILE, transcription_task)

        result = {
            "success": True,
            "file_path": str(downloaded),
            "program_name": program_name,
            "elapsed_seconds": elapsed,
        }
        print(
            f"[recorder] Complete: {program_name} "
            f"({elapsed:.0f}s) → {downloaded.name}"
        )
        return result

    except Exception as e:
        error_msg = str(e)
        update_status(
            RECORDING_TASKS_FILE, file_path, STATUS_FAILED, error=error_msg
        )
        print(
            f"[recorder] Failed: {program_name} — {error_msg}",
            file=sys.stderr,
        )
        return {
            "success": False,
            "file_path": file_path,
            "program_name": program_name,
            "error": error_msg,
        }


# ─── ワーカーループ ──────────────────────────────────────────────

def run_worker_loop():
    """タスクリストを監視し、並行ダウンロードを実行するメインループ。"""
    print(f"[recorder] Worker started (max_concurrent={MAX_CONCURRENT})")
    print(f"[recorder] Poll interval: {POLL_INTERVAL}s")
    print(f"[recorder] Output dir: {RECORDINGS_DIR}")

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    while not _shutdown_requested:
        # タイムアウトチェック
        timed_out = check_timeouts(RECORDING_TASKS_FILE, TIMEOUT_HOURS)
        if timed_out:
            print(
                f"[recorder] {len(timed_out)} task(s) timed out, "
                f"reset to pending"
            )

        # pendingタスクを取得
        pending = get_pending_tasks(RECORDING_TASKS_FILE, limit=MAX_CONCURRENT)
        if not pending:
            time.sleep(POLL_INTERVAL)
            continue

        # 並行ダウンロード
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(process_recording_task, task): task
                for task in pending
            }
            for future in as_completed(futures):
                if _shutdown_requested:
                    break
                try:
                    future.result()
                except Exception as e:
                    task = futures[future]
                    print(
                        f"[recorder] Unexpected error: "
                        f"{task['program_name']} — {e}",
                        file=sys.stderr,
                    )

        if not _shutdown_requested:
            time.sleep(POLL_INTERVAL)

    print("[recorder] Worker stopped")


# ─── 手動実行モード ──────────────────────────────────────────────

def manual_download(url: str) -> None:
    """手動で特定URLをダウンロードする。"""
    print(f"[recorder] Manual download: {url}")
    try:
        downloaded = download_program(
            source_url=url,
            output_dir=RECORDINGS_DIR,
        )
        result = {
            "success": True,
            "file_path": str(downloaded),
            "size_bytes": downloaded.stat().st_size,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="録音ワーカー — radikoタイムフリーダウンロード"
    )
    parser.add_argument(
        "--url",
        help="手動ダウンロード: radiko タイムフリーURL",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="1回だけpendingタスクを処理して終了",
    )
    args = parser.parse_args()

    if args.url:
        manual_download(args.url)
    elif args.once:
        all_results = []
        while True:
            pending = get_pending_tasks(RECORDING_TASKS_FILE, limit=9999)
            if not pending:
                break
            print(
                f"[recorder] Processing {len(pending)} pending task(s)...",
                file=sys.stderr,
            )
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
                futures = [
                    executor.submit(process_recording_task, task)
                    for task in pending
                ]
                for future in as_completed(futures):
                    result = future.result()
                    all_results.append(result)

        if not all_results:
            print("[recorder] No pending tasks", file=sys.stderr)
            summary = {
                "mode": "once",
                "total": 0,
                "success": 0,
                "failed": 0,
                "results": [],
            }
            print(json.dumps(summary, ensure_ascii=False))
            return

        success_count = sum(1 for r in all_results if r["success"])
        failed_count = len(all_results) - success_count
        summary = {
            "mode": "once",
            "total": len(all_results),
            "success": success_count,
            "failed": failed_count,
            "results": all_results,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if failed_count > 0:
            sys.exit(1)
    else:
        run_worker_loop()


if __name__ == "__main__":
    main()
