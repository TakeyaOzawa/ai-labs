#!/usr/bin/env python3.12
"""
create-daily-jobs: 日次scoutパイプラインのジョブファイルを生成する（create-jobs.pyラッパー）

目的:
    日次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
    ジョブファイル（JSON）を生成する。

使い方:
    python3.12 scripts/create-daily-jobs.py [基準日]

例:
    python3.12 scripts/create-daily-jobs.py 2026-05-04

出力: JSON形式のジョブファイル（~/Documents/works/jobs/scout_daily/）
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
    {"job_name": "tech-trend-scout", "timeout": 300, "retry_delay": 30},
    {"job_name": "biz-car-trend-scout", "timeout": 300, "retry_delay": 30},
    {
        "job_name": "academic-trend-scout-pipeline",
        "timeout": 900,
        "retry_delay": 60,
        "child_jobs": [
            {"job_name": "academic-searcher-ml_ai", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-searcher-cv_robotics", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-searcher-se_it", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-searcher-economics", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-searcher-behavioral_biz", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-searcher-interdisciplinary", "timeout": 300, "retry_delay": 30},
            {"job_name": "academic-reporter", "timeout": 300, "retry_delay": 30, "depends_on": ["academic-searcher-ml_ai", "academic-searcher-cv_robotics", "academic-searcher-se_it", "academic-searcher-economics", "academic-searcher-behavioral_biz", "academic-searcher-interdisciplinary"]},
        ],
    },
    {"job_name": "lifestyle-event-scout", "timeout": 300, "retry_delay": 30},
    {"job_name": "rss-source-updater", "timeout": 180, "retry_delay": 30},
    {"job_name": "github-public-trend-scout", "timeout": 600, "retry_delay": 60},
    {"job_name": "github-org-trend-scout", "timeout": 600, "retry_delay": 60},
    {
        "job_name": "gws-trend-scout-pipeline",
        "timeout": 900,
        "retry_delay": 60,
        "child_jobs": [
            {"job_name": "gws-extractor-docs", "timeout": 300, "retry_delay": 30},
            {"job_name": "gws-extractor-slides", "timeout": 300, "retry_delay": 30},
            {"job_name": "gws-extractor-sheets", "timeout": 300, "retry_delay": 30},
            {"job_name": "gws-extractor-forms", "timeout": 300, "retry_delay": 30},
            {"job_name": "gws-extractor-pdf", "timeout": 300, "retry_delay": 30},
            {"job_name": "markdown-reporter", "timeout": 300, "retry_delay": 30, "depends_on": ["gws-extractor-docs", "gws-extractor-slides", "gws-extractor-sheets", "gws-extractor-forms", "gws-extractor-pdf"]},
        ],
    },
    {"job_name": "slack-trend-scout", "timeout": 600, "retry_delay": 60},
    {"job_name": "notion-trend-scout", "timeout": 900, "retry_delay": 60},
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
        "--pipeline", "scout_daily",
        "--base-date", base_date,
        "--jobs", json.dumps(CHILD_JOBS, ensure_ascii=False),
        "--parent-timeout", "3600",
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
