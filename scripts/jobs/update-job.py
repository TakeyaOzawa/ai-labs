#!/usr/bin/env python3.12
"""
update-job: ジョブファイル内の特定ジョブのステータスを更新する

目的:
    パイプラインのジョブ状態遷移を管理するための抽象レイヤー。
    将来的にバックエンドをDB/APIに差し替え可能。

使い方:
    python3.12 scripts/update-job.py --job-file /path/to/file.json --job-id ID --set '{"status": "running"}'
    python3.12 scripts/update-job.py --job-file /path/to/file.json --scope parent --set '{"status": "running"}'

例:
    python3.12 scripts/update-job.py --job-file ~/Documents/works/jobs/scout_daily/2026-05-07_xxx.json --job-id 01J... --set '{"status": "running"}'

オプション:
    --job-file   必須。対象ジョブファイルのパス
    --job-id     更新対象の子ジョブID（--scope child 時に必須）
    --scope      parent: 親ジョブを更新 / child: 子ジョブを更新（デフォルト: child）
    --set        必須。更新するフィールドのJSON

出力: JSON形式
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import json
from datetime import datetime, timedelta, timezone

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
UPDATABLE_FIELDS = {"status", "status_detail", "started_at", "updated_at",
                    "completed_at", "error"}


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ジョブステータス更新")
    parser.add_argument("--job-file", required=True, help="対象ジョブファイルのパス")
    parser.add_argument("--job-id", help="更新対象の子ジョブID")
    parser.add_argument("--scope", default="child", choices=["parent", "child"],
                        help="更新スコープ（デフォルト: child）")
    parser.add_argument("--set", required=True, dest="set_json",
                        help="更新フィールドのJSON")
    args = parser.parse_args()

    job_file = Path(args.job_file)

    # バリデーション
    if not job_file.exists():
        print(json.dumps({"success": False, "error": f"Job file not found: {job_file}"}))
        sys.exit(1)

    try:
        updates = json.loads(args.set_json)
    except json.JSONDecodeError:
        print(json.dumps({"success": False, "error": "Invalid JSON in --set"}))
        sys.exit(1)

    # ジョブファイル読み込み
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # updated_at を自動付与
    if "updated_at" not in updates:
        updates["updated_at"] = now

    if args.scope == "parent":
        result = update_parent(data, updates, job_file)
    else:
        if not args.job_id:
            print(json.dumps({"success": False, "error": "--job-id is required for child scope"}))
            sys.exit(1)
        result = update_child(data, updates, args.job_id, job_file)

    # ファイル書き戻し
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False))


def update_parent(data: dict, updates: dict, job_file: Path) -> dict:
    """親ジョブを更新する。"""
    before = {k: data.get(k) for k in UPDATABLE_FIELDS}

    for key, value in updates.items():
        if key in UPDATABLE_FIELDS:
            data[key] = value

    after = {k: data.get(k) for k in UPDATABLE_FIELDS}

    return {
        "success": True,
        "job_file": str(job_file),
        "job_id": "parent",
        "scope": "parent",
        "before": before,
        "after": after,
        "message": f"Parent updated: {before.get('status')} → {after.get('status')}",
    }


def update_child(data: dict, updates: dict, job_id: str, job_file: Path) -> dict:
    """子ジョブを再帰検索して更新する。"""
    target = find_job_recursive(data.get("child_jobs", []), job_id)

    if target is None:
        return {"success": False, "error": f"Child job not found: {job_id}"}

    before = {k: target.get(k) for k in UPDATABLE_FIELDS}

    for key, value in updates.items():
        if key in UPDATABLE_FIELDS:
            target[key] = value

    after = {k: target.get(k) for k in UPDATABLE_FIELDS}

    return {
        "success": True,
        "job_file": str(job_file),
        "job_id": job_id,
        "scope": "child",
        "before": before,
        "after": after,
        "message": f"Job {job_id} updated: {before.get('status')} → {after.get('status')}",
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



if __name__ == "__main__":
    main()
