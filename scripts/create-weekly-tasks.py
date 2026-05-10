#!/usr/bin/env python3.12
"""
create-weekly-tasks: 週次scoutパイプラインのタスクファイルを生成する

目的:
    週次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
    タスクファイル（JSON）を生成する。

使い方:
    python3.12 scripts/create-weekly-tasks.py [基準日]

例:
    python3.12 scripts/create-weekly-tasks.py 2026-05-04

出力: JSON形式のタスクファイル（~/Documents/works/agent_histories/scout_weekly/）
"""

import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
DIR = Path.home() / "Documents" / "works" / "agent_histories" / "scout_weekly"

CHILD_TASKS = [
    {"task_name": "slack-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"task_name": "gws-digest-scout", "timeout": 900, "retry_delay": 60, "depends_on": None},
    {"task_name": "tech-event-scout", "timeout": 300, "retry_delay": 30, "depends_on": None},
    {"task_name": "lifestyle-event-scout", "timeout": 300, "retry_delay": 30, "depends_on": None},
    {"task_name": "tech-blog-material-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"task_name": "tech-poc-planner", "timeout": 900, "retry_delay": 60, "depends_on": "tech-blog-material-scout"},
    {"task_name": "github-org-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"task_name": "github-public-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"task_name": "notion-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"task_name": "github-verification-candidate-scout", "timeout": 600, "retry_delay": 60, "depends_on": "github-public-digest-scout"},
]


# ─── ユーティリティ ──────────────────────────────────────────────

def generate_sortable_id() -> str:
    """タイムスタンプベースのソート可能なユニークIDを生成する。"""
    ts_ms = int(time.time() * 1000)
    random_part = uuid.uuid4().hex[:8]
    return f"{ts_ms:013x}-{random_part}"


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    now = datetime.now(tz=JST)

    # 基準日: 引数 or 昨日
    if len(sys.argv) >= 2:
        base_date = sys.argv[1]
    else:
        base_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    now_str = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    task_id = generate_sortable_id()

    DIR.mkdir(parents=True, exist_ok=True)

    # 子タスク生成
    children = []
    for child_def in CHILD_TASKS:
        # depends_on があるタスクは pending、それ以外は starting
        status = "pending" if child_def["depends_on"] else "starting"
        children.append({
            "task_id": generate_sortable_id(),
            "task_name": child_def["task_name"],
            "args": {"base_date": base_date},
            "options": {
                "async": True,
                "timeout_seconds": child_def["timeout"],
                "max_retries": 1,
                "retry_delay_seconds": child_def["retry_delay"],
            },
            "status": status,
            "status_detail": None,
            "depends_on": child_def["depends_on"],
            "child_tasks": [],
            "created_at": now_str,
            "updated_at": now_str,
            "started_at": None,
            "completed_at": None,
            "error": None,
        })

    # 親タスク
    task_data = {
        "task_id": task_id,
        "task_name": "scout_weekly",
        "args": {"base_date": base_date},
        "options": {
            "async": False,
            "timeout_seconds": 7200,
            "max_retries": 0,
            "retry_delay_seconds": 0,
        },
        "status": "pending",
        "status_detail": None,
        "depends_on": None,
        "child_tasks": children,
        "created_at": now_str,
        "updated_at": now_str,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    filepath = DIR / f"{base_date}_{task_id}_scout_weekly.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

    print(f"📋 週次scoutタスクファイルを作成しました")
    print(f"   タスクID: {task_id}")
    print(f"   タスク名: scout_weekly")
    print(f"   基準日:   {base_date}")
    print(f"   子タスク: {len(children)}件")
    print(f"   ファイル: {filepath}")


if __name__ == "__main__":
    main()
