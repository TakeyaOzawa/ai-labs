#!/usr/bin/env python3.12
"""
update-task: タスクファイル内の特定タスクのステータスを更新する

目的:
    scoutパイプラインのタスク状態遷移を管理するための抽象レイヤー。
    将来的にバックエンドをDB/APIに差し替え可能。

使い方:
    python3.12 scripts/update-task.py --task-file /path/to/file.json --task-id ID --set '{"status": "running"}'
    python3.12 scripts/update-task.py --task-file /path/to/file.json --scope parent --set '{"status": "running"}'

例:
    python3.12 scripts/update-task.py --task-file ~/Documents/works/agent_histories/scout_daily/2026-05-07_xxx.json --task-id 01J... --set '{"status": "running"}'

オプション:
    --task-file  必須。対象タスクファイルのパス
    --task-id    更新対象の子タスクID（--scope child 時に必須）
    --scope      parent: 親タスクを更新 / child: 子タスクを更新（デフォルト: child）
    --set        必須。更新するフィールドのJSON

出力: JSON形式
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
UPDATABLE_FIELDS = {"status", "status_detail", "started_at", "updated_at",
                    "completed_at", "error"}


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="タスクステータス更新")
    parser.add_argument("--task-file", required=True, help="対象タスクファイルのパス")
    parser.add_argument("--task-id", help="更新対象の子タスクID")
    parser.add_argument("--scope", default="child", choices=["parent", "child"],
                        help="更新スコープ（デフォルト: child）")
    parser.add_argument("--set", required=True, dest="set_json",
                        help="更新フィールドのJSON")
    args = parser.parse_args()

    task_file = Path(args.task_file)

    # バリデーション
    if not task_file.exists():
        print(json.dumps({"success": False, "error": f"Task file not found: {task_file}"}))
        sys.exit(1)

    try:
        updates = json.loads(args.set_json)
    except json.JSONDecodeError:
        print(json.dumps({"success": False, "error": "Invalid JSON in --set"}))
        sys.exit(1)

    # タスクファイル読み込み
    with open(task_file, encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # updated_at を自動付与
    if "updated_at" not in updates:
        updates["updated_at"] = now

    if args.scope == "parent":
        result = update_parent(data, updates, task_file)
    else:
        if not args.task_id:
            print(json.dumps({"success": False, "error": "--task-id is required for child scope"}))
            sys.exit(1)
        result = update_child(data, updates, args.task_id, task_file)

    # ファイル書き戻し
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False))


def update_parent(data: dict, updates: dict, task_file: Path) -> dict:
    """親タスクを更新する。"""
    before = {k: data.get(k) for k in UPDATABLE_FIELDS}

    for key, value in updates.items():
        if key in UPDATABLE_FIELDS:
            data[key] = value

    after = {k: data.get(k) for k in UPDATABLE_FIELDS}

    return {
        "success": True,
        "task_file": str(task_file),
        "task_id": "parent",
        "scope": "parent",
        "before": before,
        "after": after,
        "message": f"Parent updated: {before.get('status')} → {after.get('status')}",
    }


def update_child(data: dict, updates: dict, task_id: str, task_file: Path) -> dict:
    """子タスクを更新する。"""
    child_tasks = data.get("child_tasks", [])

    # 対象タスクを検索
    target = None
    for task in child_tasks:
        if task.get("task_id") == task_id:
            target = task
            break

    if target is None:
        return {"success": False, "error": f"Child task not found: {task_id}"}

    before = {k: target.get(k) for k in UPDATABLE_FIELDS}

    for key, value in updates.items():
        if key in UPDATABLE_FIELDS:
            target[key] = value

    after = {k: target.get(k) for k in UPDATABLE_FIELDS}

    return {
        "success": True,
        "task_file": str(task_file),
        "task_id": task_id,
        "scope": "child",
        "before": before,
        "after": after,
        "message": f"Task {task_id} updated: {before.get('status')} → {after.get('status')}",
    }


if __name__ == "__main__":
    main()
