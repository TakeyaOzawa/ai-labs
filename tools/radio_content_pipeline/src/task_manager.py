#!/usr/bin/env python3.12
"""
task_manager: タスクリスト管理モジュール

目的:
    録音・文字起こしパイプラインのタスクキューをJSONファイルで管理する。
    複数プロセスからの同時アクセスに対応し、重複排除・タイムアウト検知を行う。

使い方:
    python3.12 src/task_manager.py --status
    python3.12 src/task_manager.py --retry-failed
    python3.12 src/task_manager.py --add recording --file /data/recordings/TBS_test.m4a

出力: JSON（標準出力）
依存: なし（標準ライブラリのみ）
"""
import argparse
import fcntl
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

DEFAULT_TIMEOUT_HOURS = 6

STATE_DIR = Path("/app/state")
RECORDING_TASKS_FILE = STATE_DIR / "recording-tasks.json"
TRANSCRIPTION_TASKS_FILE = STATE_DIR / "transcription-tasks.json"


# ─── タスクデータ構造 ────────────────────────────────────────────

def create_task(
    file_path: str,
    program_name: str,
    station_id: str,
    source_url: str = "",
    metadata: dict | None = None,
) -> dict:
    """新規タスクエントリを生成する。

    Args:
        file_path: 出力ファイルパス（重複排除のキー）
        program_name: 番組名
        station_id: 放送局ID
        source_url: ダウンロード元URL
        metadata: 追加メタデータ（放送日時等）

    Returns:
        タスクエントリのdict
    """
    now = datetime.now(JST).isoformat()
    return {
        "file_path": file_path,
        "program_name": program_name,
        "station_id": station_id,
        "source_url": source_url,
        "status": STATUS_PENDING,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "metadata": metadata or {},
    }


# ─── ファイルロック付きJSON操作 ──────────────────────────────────

def _read_tasks_file(tasks_file: Path) -> list[dict]:
    """タスクファイルを読み込む（ファイルが存在しない場合は空リスト）。"""
    if not tasks_file.exists():
        return []
    content = tasks_file.read_text(encoding="utf-8")
    if not content.strip():
        return []
    return json.loads(content)


def _write_tasks_file(tasks_file: Path, tasks: list[dict]) -> None:
    """タスクファイルに書き込む。"""
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _with_file_lock(tasks_file: Path, operation):
    """ファイルロックを取得してoperationを実行する。

    Args:
        tasks_file: タスクファイルパス
        operation: tasks(list[dict])を受け取り、(result, tasks)を返す関数

    Returns:
        operationの戻り値のresult部分
    """
    lock_file = tasks_file.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_file, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            tasks = _read_tasks_file(tasks_file)
            result, updated_tasks = operation(tasks)
            if updated_tasks is not None:
                _write_tasks_file(tasks_file, updated_tasks)
            return result
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# ─── 公開API ────────────────────────────────────────────────────

def add_task(tasks_file: Path, task: dict) -> bool:
    """タスクを追加する（重複排除付き）。

    重複排除ルール:
    - 同一file_pathのタスクがpending/processing/successの場合 → 追加しない
    - failedの場合 → 新規pendingとして追加可能

    Args:
        tasks_file: タスクファイルパス
        task: 追加するタスクエントリ

    Returns:
        追加された場合True、重複でスキップされた場合False
    """
    def _operation(tasks: list[dict]) -> tuple[bool, list[dict] | None]:
        for existing in tasks:
            if existing["file_path"] == task["file_path"]:
                if existing["status"] in (
                    STATUS_PENDING, STATUS_PROCESSING, STATUS_SUCCESS
                ):
                    return False, None
        tasks.append(task)
        return True, tasks

    return _with_file_lock(tasks_file, _operation)


def get_pending_tasks(
    tasks_file: Path,
    limit: int = 1,
) -> list[dict]:
    """pendingステータスのタスクを取得する（古い順）。

    Args:
        tasks_file: タスクファイルパス
        limit: 取得件数上限

    Returns:
        pendingタスクのリスト
    """
    def _operation(tasks: list[dict]) -> tuple[list[dict], None]:
        pending = [t for t in tasks if t["status"] == STATUS_PENDING]
        pending.sort(key=lambda t: t["created_at"])
        return pending[:limit], None

    return _with_file_lock(tasks_file, _operation)


def update_status(
    tasks_file: Path,
    file_path: str,
    new_status: str,
    error: str | None = None,
) -> bool:
    """タスクのステータスを更新する。

    Args:
        tasks_file: タスクファイルパス
        file_path: 対象タスクのfile_path
        new_status: 新しいステータス
        error: エラーメッセージ（failed時）

    Returns:
        更新された場合True
    """
    now = datetime.now(JST).isoformat()

    def _operation(tasks: list[dict]) -> tuple[bool, list[dict] | None]:
        for task in tasks:
            if task["file_path"] == file_path:
                task["status"] = new_status
                task["updated_at"] = now
                if new_status == STATUS_PROCESSING:
                    task["started_at"] = now
                elif new_status in (STATUS_SUCCESS, STATUS_FAILED):
                    task["completed_at"] = now
                if error is not None:
                    task["error"] = error
                return True, tasks
        return False, None

    return _with_file_lock(tasks_file, _operation)


def check_timeouts(
    tasks_file: Path,
    timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
) -> list[dict]:
    """processingステータスがタイムアウトしたタスクをpendingに戻す。

    Args:
        tasks_file: タスクファイルパス
        timeout_hours: タイムアウト時間（時間）

    Returns:
        タイムアウトでpendingに戻されたタスクのリスト
    """
    now = datetime.now(JST)

    def _operation(tasks: list[dict]) -> tuple[list[dict], list[dict] | None]:
        timed_out = []
        modified = False
        for task in tasks:
            if task["status"] == STATUS_PROCESSING and task["started_at"]:
                started = datetime.fromisoformat(task["started_at"])
                if (now - started).total_seconds() > timeout_hours * 3600:
                    task["status"] = STATUS_PENDING
                    task["updated_at"] = now.isoformat()
                    task["started_at"] = None
                    task["error"] = (
                        f"Timeout: processing exceeded {timeout_hours}h"
                    )
                    timed_out.append(task)
                    modified = True
        return timed_out, tasks if modified else None

    return _with_file_lock(tasks_file, _operation)


def retry_failed(tasks_file: Path) -> list[dict]:
    """failedステータスのタスクをpendingに戻す。

    Args:
        tasks_file: タスクファイルパス

    Returns:
        pendingに戻されたタスクのリスト
    """
    now = datetime.now(JST).isoformat()

    def _operation(tasks: list[dict]) -> tuple[list[dict], list[dict] | None]:
        retried = []
        modified = False
        for task in tasks:
            if task["status"] == STATUS_FAILED:
                task["status"] = STATUS_PENDING
                task["updated_at"] = now
                task["started_at"] = None
                task["completed_at"] = None
                task["error"] = None
                retried.append(task)
                modified = True
        return retried, tasks if modified else None

    return _with_file_lock(tasks_file, _operation)


def get_all_tasks(tasks_file: Path) -> list[dict]:
    """全タスクを取得する。"""
    def _operation(tasks: list[dict]) -> tuple[list[dict], None]:
        return tasks, None

    return _with_file_lock(tasks_file, _operation)


def get_status_summary(tasks_file: Path) -> dict[str, int]:
    """ステータス別のタスク件数を取得する。

    Returns:
        {"pending": N, "processing": N, "success": N, "failed": N, "total": N}
    """
    tasks = get_all_tasks(tasks_file)
    summary = {
        STATUS_PENDING: 0,
        STATUS_PROCESSING: 0,
        STATUS_SUCCESS: 0,
        STATUS_FAILED: 0,
        "total": len(tasks),
    }
    for task in tasks:
        status = task.get("status", STATUS_PENDING)
        if status in summary:
            summary[status] += 1
    return summary


def is_all_done(tasks_file: Path) -> bool:
    """全タスクがsuccess/failedのいずれかであるか判定する。"""
    tasks = get_all_tasks(tasks_file)
    if not tasks:
        return True
    return all(
        t["status"] in (STATUS_SUCCESS, STATUS_FAILED) for t in tasks
    )


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="タスクリスト管理（録音・文字起こしパイプライン）"
    )
    parser.add_argument(
        "--file",
        choices=["recording", "transcription"],
        default="recording",
        help="対象タスクファイル（default: recording）",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="ステータスサマリーを表示",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="全タスクを表示",
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="failedタスクをpendingに戻す",
    )
    parser.add_argument(
        "--check-timeouts", action="store_true",
        help="タイムアウトしたタスクをpendingに戻す",
    )
    parser.add_argument(
        "--add", metavar="FILE_PATH",
        help="タスクを手動追加（file_pathを指定）",
    )
    parser.add_argument(
        "--program-name", default="manual",
        help="手動追加時の番組名",
    )
    parser.add_argument(
        "--station-id", default="",
        help="手動追加時の放送局ID",
    )
    parser.add_argument(
        "--source-url", default="",
        help="手動追加時のソースURL",
    )
    args = parser.parse_args()

    tasks_file = (
        RECORDING_TASKS_FILE if args.file == "recording"
        else TRANSCRIPTION_TASKS_FILE
    )

    if args.status:
        summary = get_status_summary(tasks_file)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    elif args.list:
        tasks = get_all_tasks(tasks_file)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    elif args.retry_failed:
        retried = retry_failed(tasks_file)
        result = {
            "success": True,
            "retried_count": len(retried),
            "tasks": [t["file_path"] for t in retried],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.check_timeouts:
        timed_out = check_timeouts(tasks_file)
        result = {
            "success": True,
            "timed_out_count": len(timed_out),
            "tasks": [t["file_path"] for t in timed_out],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.add:
        task = create_task(
            file_path=args.add,
            program_name=args.program_name,
            station_id=args.station_id,
            source_url=args.source_url,
        )
        added = add_task(tasks_file, task)
        result = {"success": True, "added": added, "file_path": args.add}
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
