#!/usr/bin/env python3.12
"""
create-jobs: 汎用パイプラインジョブファイル生成

目的:
    任意のパイプラインのジョブファイル（JSON）を生成する。
    パイプライン名とジョブ定義を受け取り、標準形式のジョブファイルを出力する。

使い方:
    python3.12 scripts/create-jobs.py --pipeline {name} --base-date YYYY-MM-DD --jobs-file /path/to/jobs-def.json
    python3.12 scripts/create-jobs.py --pipeline {name} --base-date YYYY-MM-DD --jobs '[...]'

例:
    python3.12 scripts/create-jobs.py --pipeline scout_daily --base-date 2026-05-10 --jobs-file ~/jobs-def.json
    python3.12 scripts/create-jobs.py --pipeline my_pipeline --base-date 2026-05-10 --jobs '[{"job_name":"agent-a","timeout":300,"retry_delay":30,"depends_on":null}]'

出力: JSON形式のジョブファイル（~/Documents/works/jobs/{pipeline}/）
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
BASE_DIR = Path.home() / "Documents" / "works" / "jobs"


# ─── ユーティリティ ──────────────────────────────────────────────

def generate_sortable_id() -> str:
    """タイムスタンプベースのソート可能なユニークIDを生成する。

    ULID互換のソート特性を持つ: タイムスタンプ(ms) + ランダム部分
    フォーマット: TTTTTTTTTT-RRRRRRRR（13桁hex timestamp + 8桁hex random）
    """
    ts_ms = int(time.time() * 1000)
    random_part = uuid.uuid4().hex[:8]
    return f"{ts_ms:013x}-{random_part}"


def load_jobs(args: argparse.Namespace) -> list[dict]:
    """ジョブ定義を読み込む。--jobs-file または --jobs から。"""
    if args.jobs_file:
        jobs_path = Path(args.jobs_file).expanduser()
        if not jobs_path.exists():
            print(f"❌ ジョブ定義ファイルが見つかりません: {jobs_path}", file=sys.stderr)
            sys.exit(1)
        with open(jobs_path, encoding="utf-8") as f:
            return json.load(f)
    elif args.jobs:
        try:
            return json.loads(args.jobs)
        except json.JSONDecodeError as e:
            print(f"❌ --jobs のJSON解析に失敗: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("❌ --jobs-file または --jobs のいずれかを指定してください", file=sys.stderr)
        sys.exit(1)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="汎用パイプラインジョブファイル生成")
    parser.add_argument("--pipeline", required=True, help="パイプライン名（出力ディレクトリ名）")
    parser.add_argument("--base-date", help="基準日（YYYY-MM-DD）。省略時は昨日")
    parser.add_argument("--jobs-file", help="ジョブ定義JSONファイルのパス")
    parser.add_argument("--jobs", help="ジョブ定義のJSON文字列（インライン指定）")
    parser.add_argument("--parent-timeout", type=int, default=3600,
                        help="親ジョブのタイムアウト秒（デフォルト: 3600）")
    args = parser.parse_args()

    now = datetime.now(tz=JST)

    # 基準日
    if args.base_date:
        base_date = args.base_date
    else:
        base_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # ジョブ定義読み込み
    job_defs = load_jobs(args)

    if not job_defs:
        print("❌ ジョブ定義が空です", file=sys.stderr)
        sys.exit(1)

    now_str = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    job_id = generate_sortable_id()

    # 出力ディレクトリ
    output_dir = BASE_DIR / args.pipeline
    output_dir.mkdir(parents=True, exist_ok=True)

    # 子ジョブ生成
    children = []
    for job_def in job_defs:
        job_name = job_def.get("job_name")
        if not job_name:
            print("❌ job_name が未指定のジョブ定義があります", file=sys.stderr)
            sys.exit(1)

        depends_on = job_def.get("depends_on")
        status = "pending" if depends_on else "starting"

        children.append({
            "job_id": generate_sortable_id(),
            "job_name": job_name,
            "args": {"base_date": base_date},
            "options": {
                "async": True,
                "timeout_seconds": job_def.get("timeout", 300),
                "max_retries": job_def.get("max_retries", 1),
                "retry_delay_seconds": job_def.get("retry_delay", 30),
            },
            "status": status,
            "status_detail": None,
            "depends_on": depends_on,
            "child_jobs": [],
            "created_at": now_str,
            "updated_at": now_str,
            "started_at": None,
            "completed_at": None,
            "error": None,
        })

    # 親ジョブ
    job_data = {
        "job_id": job_id,
        "job_name": args.pipeline,
        "args": {"base_date": base_date},
        "options": {
            "async": False,
            "timeout_seconds": args.parent_timeout,
            "max_retries": 0,
            "retry_delay_seconds": 0,
        },
        "status": "pending",
        "status_detail": None,
        "depends_on": None,
        "child_jobs": children,
        "created_at": now_str,
        "updated_at": now_str,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    filepath = output_dir / f"{base_date}_{job_id}_{args.pipeline}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2)

    print(f"📋 ジョブファイルを作成しました")
    print(f"   ジョブID: {job_id}")
    print(f"   ジョブ名: {args.pipeline}")
    print(f"   基準日:   {base_date}")
    print(f"   子ジョブ: {len(children)}件")
    print(f"   ファイル: {filepath}")


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
