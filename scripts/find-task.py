#!/usr/bin/env python3.12
"""
find-task: タスクファイルからタスクを検索しJSON形式で出力する

目的:
    scoutパイプラインのタスク管理において、タスクの状態確認や
    特定タスクの検索を行うための抽象レイヤー。
    将来的にバックエンドをDB/APIに差し替え可能。

使い方:
    python3.12 scripts/find-task.py --pipeline daily|weekly [--date YYYY-MM-DD] [--status STATUS] [--task-id ID] [--task-name NAME] [--scope parent|child] [--limit N]

例:
    python3.12 scripts/find-task.py --pipeline daily --date 2026-05-07
    python3.12 scripts/find-task.py --pipeline weekly --status running --limit 5

オプション:
    --pipeline   必須。daily または weekly
    --date       基準日（省略時: 最新のタスクファイルを使用）
    --status     フィルタするステータス（starting, running, pending, completed, failed）
    --task-id    特定のtask_idで検索
    --task-name  特定のtask_nameで検索
    --scope      parent: 親タスクのみ返す / child: 子タスクのみ返す（デフォルト: child）
    --limit      返す件数の上限（デフォルト: 1）

出力: JSON形式
"""

import argparse
import json
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Documents" / "works" / "agent_histories"

PIPELINE_DIRS: dict[str, Path] = {
    "daily": BASE_DIR / "scout_daily",
    "weekly": BASE_DIR / "scout_weekly",
}


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="タスクファイル検索")
    parser.add_argument("--pipeline", required=True, choices=["daily", "weekly"],
                        help="パイプライン種別")
    parser.add_argument("--date", help="基準日（YYYY-MM-DD）")
    parser.add_argument("--status", help="ステータスフィルタ")
    parser.add_argument("--task-id", help="タスクIDで検索")
    parser.add_argument("--task-name", help="タスク名で検索")
    parser.add_argument("--scope", default="child", choices=["parent", "child"],
                        help="検索スコープ（デフォルト: child）")
    parser.add_argument("--limit", type=int, default=1,
                        help="返す件数の上限（デフォルト: 1）")
    args = parser.parse_args()

    task_dir = PIPELINE_DIRS[args.pipeline]

    # タスクファイル特定
    task_file = find_task_file(task_dir, args.date)
    if task_file is None:
        print(json.dumps({
            "found": False,
            "error": "No task file found",
            "task_file": None,
            "tasks": [],
            "parent": None,
        }))
        return

    # タスクファイル読み込み
    with open(task_file, encoding="utf-8") as f:
        data = json.load(f)

    # 親タスク情報
    parent = {
        k: data.get(k)
        for k in ["task_id", "task_name", "status", "status_detail",
                  "args", "started_at", "updated_at", "completed_at", "error"]
    }

    # scope=parent の場合
    if args.scope == "parent":
        print(json.dumps({
            "found": True,
            "task_file": str(task_file),
            "tasks": [parent],
            "parent": parent,
        }, ensure_ascii=False))
        return

    # 子タスクのフィルタリング
    tasks = data.get("child_tasks", [])

    if args.status:
        tasks = [t for t in tasks if t.get("status") == args.status]

    if args.task_id:
        tasks = [t for t in tasks if t.get("task_id") == args.task_id]

    if args.task_name:
        tasks = [t for t in tasks if t.get("task_name") == args.task_name]

    tasks = tasks[:args.limit]
    found = len(tasks) > 0

    print(json.dumps({
        "found": found,
        "task_file": str(task_file),
        "tasks": tasks,
        "parent": parent,
    }, ensure_ascii=False))


def find_task_file(task_dir: Path, date: str | None) -> Path | None:
    """タスクファイルを特定する。"""
    if not task_dir.exists():
        return None

    json_files = sorted(task_dir.glob("*.json"))
    if not json_files:
        return None

    if date:
        # 指定日のファイルを検索
        matching = [f for f in json_files if f.name.startswith(date)]
        return matching[0] if matching else None
    else:
        # 最新のファイル（名前ソートで最後）
        return json_files[-1]


if __name__ == "__main__":
    main()
