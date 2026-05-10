#!/usr/bin/env python3.12
"""
create-daily-tasks: 日次scoutパイプラインのタスクファイルを生成する

目的:
    日次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
    タスクファイル（JSON）を生成する。

使い方:
    python3.12 scripts/create-daily-tasks.py [基準日]

例:
    python3.12 scripts/create-daily-tasks.py 2026-05-04

出力: JSON形式のタスクファイル（~/Documents/works/agent_histories/scout_daily/）
"""

import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
DIR = Path.home() / "Documents" / "works" / "agent_histories" / "scout_daily"

CHILD_TASKS = [
    {"task_name": "tech-trend-scout", "timeout": 300, "retry_delay": 30},
    {"task_name": "biz-car-trend-scout", "timeout": 300, "retry_delay": 30},
    {"task_name": "academic-trend-scout", "timeout": 300, "retry_delay": 30},
    {"task_name": "slack-trend-scout", "timeout": 600, "retry_delay": 60},
    {"task_name": "gws-trend-scout", "timeout": 900, "retry_delay": 60},
    {"task_name": "github-org-trend-scout", "timeout": 600, "retry_delay": 60},
    {"task_name": "github-public-trend-scout", "timeout": 600, "retry_delay": 60},
    {"task_name": "notion-trend-scout", "timeout": 900, "retry_delay": 60},
]


# ─── ユーティリティ ──────────────────────────────────────────────

def generate_sortable_id() -> str:
    """タイムスタンプベースのソート可能なユニークIDを生成する。

    ULID互換のソート特性を持つ: タイムスタンプ(ms) + ランダム部分
    フォーマット: TTTTTTTTTT-RRRRRRRR（10桁hex timestamp + 8桁hex random）
    """
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
            "status": "starting",
            "status_detail": None,
            "depends_on": None,
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
        "task_name": "scout_daily",
        "args": {"base_date": base_date},
        "options": {
            "async": False,
            "timeout_seconds": 3600,
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

    filepath = DIR / f"{base_date}_{task_id}_scout_daily.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

    print(f"📋 日次scoutタスクファイルを作成しました")
    print(f"   タスクID: {task_id}")
    print(f"   タスク名: daily-scout")
    print(f"   基準日:   {base_date}")
    print(f"   子タスク: {len(children)}件")
    print(f"   ファイル: {filepath}")


if __name__ == "__main__":
    main()
