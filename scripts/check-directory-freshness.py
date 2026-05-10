#!/usr/bin/env python3.12
"""
check-directory-freshness: ユーザーディレクトリの鮮度を確認する

目的:
    Slack/Notionユーザーデータの日付ディレクトリが古くなっていないかを検知し、
    更新が必要なタイミングを判定する。最終更新から指定日数以上経過していれば stale と判定。

使い方:
    python3.12 scripts/check-directory-freshness.py --type slack --max-age-days 7
    python3.12 scripts/check-directory-freshness.py --type notion --max-age-days 14

出力: JSON形式
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

BASE_DIRS: dict[str, Path] = {
    "slack": Path.home() / "Documents" / "works" / "slack_users",
    "notion": Path.home() / "Documents" / "works" / "notion_users",
}


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ユーザーディレクトリの鮮度確認")
    parser.add_argument("--type", required=True, choices=["slack", "notion"],
                        help="チェック対象タイプ")
    parser.add_argument("--max-age-days", type=int, default=7,
                        help="stale判定の閾値日数（デフォルト: 7）")
    args = parser.parse_args()

    dir_type: str = args.type
    max_age_days: int = args.max_age_days
    base_dir = BASE_DIRS[dir_type]

    # 最新の日付ディレクトリを特定（20XX-XX-XX形式）
    date_dirs = sorted(
        [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("20")],
        reverse=True,
    ) if base_dir.exists() else []

    if not date_dirs:
        result = {
            "stale": True,
            "type": dir_type,
            "last_updated": None,
            "age_days": 999,
            "max_age_days": max_age_days,
        }
        print(json.dumps(result))
        return

    latest_date_str = date_dirs[0].name
    today = datetime.now(tz=JST).date()

    try:
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
    except ValueError:
        # パース失敗時はstale扱い
        result = {
            "stale": True,
            "type": dir_type,
            "last_updated": latest_date_str,
            "age_days": 999,
            "max_age_days": max_age_days,
        }
        print(json.dumps(result))
        return

    age_days = (today - latest_date).days
    stale = age_days >= max_age_days

    result = {
        "stale": stale,
        "type": dir_type,
        "last_updated": latest_date_str,
        "age_days": age_days,
        "max_age_days": max_age_days,
    }
    print(json.dumps(result))



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
