"""job_manager: ports.JobRepository の実装（ファイルI/O依存）。"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .models import Step
except ImportError:
    from models import Step

JST = timezone(timedelta(hours=9))


def _now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _generate_id() -> str:
    """ジョブID用のユニークIDを生成する。"""
    return uuid.uuid4().hex[:12]


def _step_to_job(step: Step) -> dict:
    """Step → ジョブ定義の変換（再帰的）。"""
    job: dict = {
        "job_id": _generate_id(),
        "job_name": step.name,
        "status": "pending",
        "timeout": step.timeout,
    }
    if step.retry:
        job["retry_delay"] = step.retry.delay
        job["max_attempts"] = step.retry.max_attempts
    if step.depends_on:
        job["depends_on"] = step.depends_on
    if step.steps:
        job["child_jobs"] = [_step_to_job(s) for s in step.steps]
    return job


def _find_job_id_by_name(jobs: list[dict], job_name: str) -> str:
    """ジョブツリーを再帰的に探索し、指定名のジョブIDを返す。"""
    for job in jobs:
        if job.get("job_name") == job_name:
            return job.get("job_id", "")
        found = _find_job_id_by_name(job.get("child_jobs", []), job_name)
        if found:
            return found
    return ""


@dataclass
class FileJobRepository:
    """ジョブファイルベースのリポジトリ実装（ports.JobRepository準拠）。"""

    job_dir: Path
    update_script: Path

    def generate(self, pipeline_name: str, base_date: str, steps: list[Step]) -> Path:
        """Step ツリーからジョブファイルを自動生成する。"""
        self.job_dir.mkdir(parents=True, exist_ok=True)

        parent_id = _generate_id()
        parent_job = {
            "job_id": parent_id,
            "job_name": pipeline_name,
            "base_date": base_date,
            "status": "running",
            "started_at": _now_jst(),
            "timeout": sum(s.timeout for s in steps),
            "child_jobs": [_step_to_job(s) for s in steps],
        }

        file_path = self.job_dir / f"{base_date}_{pipeline_name}.json"
        file_path.write_text(
            json.dumps(parent_job, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return file_path

    def update(self, job_file: Path, job_id: str, updates: dict, scope: str = "child") -> None:
        """ジョブを更新する。"""
        if not updates:
            return
        cmd = [
            "python3.12",
            str(self.update_script),
            "--job-file",
            str(job_file),
            "--scope",
            scope if scope == "parent" else "child",
            "--set",
            json.dumps(updates, ensure_ascii=False),
        ]
        if scope != "parent" and job_id:
            cmd.extend(["--job-id", job_id])
        subprocess.run(cmd, capture_output=True, text=True)

    def find_child_id(self, job_file: Path, job_name: str) -> str:
        """ジョブファイルから指定ジョブ名のIDを再帰検索で取得する。"""
        with open(job_file, encoding="utf-8") as f:
            data = json.load(f)
        return _find_job_id_by_name(data.get("child_jobs", []), job_name)
