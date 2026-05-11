#!/usr/bin/env python3.12
"""
find-job: ジョブファイルからジョブを検索しJSON形式で出力する

目的:
    パイプラインのジョブ管理において、ジョブの状態確認や
    特定ジョブの検索を行うための抽象レイヤー。
    将来的にバックエンドをDB/APIに差し替え可能。

使い方:
    python3.12 scripts/find-job.py --pipeline PIPELINE [--date YYYY-MM-DD] [--status STATUS] [--job-id ID] [--job-name NAME] [--scope parent|child] [--limit N]

例:
    python3.12 scripts/find-job.py --pipeline daily --date 2026-05-07
    python3.12 scripts/find-job.py --pipeline weekly --status running --limit 5

オプション:
    --pipeline   必須。パイプライン名（daily, weekly, または任意のパイプライン名）
    --date       基準日（省略時: 最新のジョブファイルを使用）
    --status     フィルタするステータス（starting, running, pending, completed, failed）
    --job-id     特定のjob_idで検索
    --job-name   特定のjob_nameで検索
    --scope      parent: 親ジョブのみ返す / child: 子ジョブのみ返す（デフォルト: child）
    --limit      返す件数の上限（デフォルト: 1）

出力: JSON形式
"""

import argparse
import json
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Documents" / "works" / "jobs"

# 後方互換マッピング（既存パイプライン用）
PIPELINE_ALIASES: dict[str, str] = {
    "daily": "scout_daily",
    "weekly": "scout_weekly",
}


def resolve_pipeline_dir(pipeline: str) -> Path:
    """パイプライン名からディレクトリパスを解決する。"""
    dir_name = PIPELINE_ALIASES.get(pipeline, pipeline)
    return BASE_DIR / dir_name


# ─── 再帰検索・ツリー表示 ────────────────────────────────────────

STATUS_ICONS: dict[str, str] = {
    "completed": "✅",
    "running": "🔄",
    "failed": "❌",
    "starting": "⏳",
    "pending": "⏸️",
}


def find_job_recursive(jobs: list[dict], job_id: str) -> dict | None:
    """ジョブツリーを再帰的に探索し、指定IDのジョブを返す。"""
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
        found = find_job_recursive(job.get("child_jobs", []), job_id)
        if found is not None:
            return found
    return None


def find_jobs_recursive(jobs: list[dict], job_name: str) -> list[dict]:
    """ジョブツリーを再帰的に探索し、指定名のジョブを全て返す。"""
    results: list[dict] = []
    for job in jobs:
        if job.get("job_name") == job_name:
            results.append(job)
        results.extend(find_jobs_recursive(job.get("child_jobs", []), job_name))
    return results


def print_job_tree(data: dict, indent: int = 0) -> None:
    """ジョブツリーをインデント付きで標準出力に表示する。"""
    prefix = "  " * indent
    status = data.get("status", "unknown")
    icon = STATUS_ICONS.get(status, "❓")
    name = data.get("job_name", "unknown")
    job_id = data.get("job_id", "")[:12]

    detail = ""
    if data.get("error"):
        detail = f" error={data['error']}"
    elif data.get("status_detail"):
        detail = f" ({data['status_detail']})"

    print(f"{prefix}{icon} {name} [{status}] id={job_id}...{detail}")

    for child in data.get("child_jobs", []):
        print_job_tree(child, indent + 1)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ジョブファイル検索")
    parser.add_argument("--pipeline", required=True,
                        help="パイプライン名（daily, weekly, または任意のパイプライン名）")
    parser.add_argument("--date", help="基準日（YYYY-MM-DD）")
    parser.add_argument("--status", help="ステータスフィルタ")
    parser.add_argument("--job-id", help="ジョブIDで検索")
    parser.add_argument("--job-name", help="ジョブ名で検索")
    parser.add_argument("--scope", default="child", choices=["parent", "child"],
                        help="検索スコープ（デフォルト: child）")
    parser.add_argument("--limit", type=int, default=1,
                        help="返す件数の上限（デフォルト: 1）")
    parser.add_argument("--tree", action="store_true",
                        help="ジョブツリーをインデント付きで表示")
    args = parser.parse_args()

    job_dir = resolve_pipeline_dir(args.pipeline)

    # ジョブファイル特定
    job_file = find_job_file(job_dir, args.date)
    if job_file is None:
        print(json.dumps({
            "found": False,
            "error": "No job file found",
            "job_file": None,
            "jobs": [],
            "parent": None,
        }))
        return

    # ジョブファイル読み込み
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)

    # --tree: ツリー表示モード
    if args.tree:
        print_job_tree(data)
        return

    # 親ジョブ情報
    parent = {
        k: data.get(k)
        for k in ["job_id", "job_name", "status", "status_detail",
                  "args", "started_at", "updated_at", "completed_at", "error"]
    }

    # scope=parent の場合
    if args.scope == "parent":
        print(json.dumps({
            "found": True,
            "job_file": str(job_file),
            "jobs": [parent],
            "parent": parent,
        }, ensure_ascii=False))
        return

    # --job-id / --job-name: ツリー全体を再帰検索
    if args.job_id:
        found = find_job_recursive(data.get("child_jobs", []), job_id=args.job_id)
        jobs = [found] if found else []
    elif args.job_name:
        jobs = find_jobs_recursive(
            data.get("child_jobs", []), job_name=args.job_name,
        )
    else:
        # フラット検索（第一階層のみ、後方互換）
        jobs = data.get("child_jobs", [])

    if args.status:
        jobs = [j for j in jobs if j.get("status") == args.status]

    jobs = jobs[:args.limit]
    found = len(jobs) > 0

    print(json.dumps({
        "found": found,
        "job_file": str(job_file),
        "jobs": jobs,
        "parent": parent,
    }, ensure_ascii=False))


def find_job_file(job_dir: Path, date: str | None) -> Path | None:
    """ジョブファイルを特定する。"""
    if not job_dir.exists():
        return None

    json_files = sorted(job_dir.glob("*.json"))
    if not json_files:
        return None

    if date:
        # 指定日のファイルを検索
        matching = [f for f in json_files if f.name.startswith(date)]
        return matching[0] if matching else None
    else:
        # 最新のファイル（名前ソートで最後）
        return json_files[-1]


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
