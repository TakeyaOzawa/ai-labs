#!/usr/bin/env python3.12
"""
create-weekly-jobs: 週次scoutパイプラインのジョブファイルを生成する（create-jobs.pyラッパー）

目的:
    週次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
    ジョブファイル（JSON）を生成する。

使い方:
    python3.12 scripts/create-weekly-jobs.py [基準日]

例:
    python3.12 scripts/create-weekly-jobs.py 2026-05-04

出力: JSON形式のジョブファイル（~/Documents/works/jobs/scout_weekly/）
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
SCRIPTS_DIR = Path(__file__).parent

CHILD_JOBS = [
    {"job_name": "tech-event-scout", "timeout": 300, "retry_delay": 30, "depends_on": None},
    {"job_name": "github-public-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"job_name": "github-org-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"job_name": "tech-blog-material-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"job_name": "github-verification-candidate-scout", "timeout": 600, "retry_delay": 60, "depends_on": ["github-public-digest-scout", "tech-blog-material-scout"]},
    {"job_name": "tech-poc-planner", "timeout": 900, "retry_delay": 60, "depends_on": ["tech-blog-material-scout", "github-verification-candidate-scout"]},
    {"job_name": "gws-digest-scout", "timeout": 900, "retry_delay": 60, "depends_on": None},
    {"job_name": "slack-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
    {"job_name": "notion-digest-scout", "timeout": 600, "retry_delay": 60, "depends_on": None},
]


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    # 基準日: 引数 or 昨日
    if len(sys.argv) >= 2:
        base_date = sys.argv[1]
    else:
        yesterday = datetime.now(tz=JST) - timedelta(days=1)
        base_date = yesterday.strftime("%Y-%m-%d")

    # create-jobs.py に委譲
    cmd = [
        "python3.12", str(SCRIPTS_DIR / "create-jobs.py"),
        "--pipeline", "scout_weekly",
        "--base-date", base_date,
        "--jobs", json.dumps(CHILD_JOBS, ensure_ascii=False),
        "--parent-timeout", "7200",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    # 出力をそのまま標準出力に転送（呼び出し元がcapture_outputで取得できるように）
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    sys.exit(result.returncode)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
