"""test_job_lifecycle: ジョブライフサイクルの結合テスト。"""

import json
from pathlib import Path

import pytest

from job_manager import FileJobRepository, _find_job_id_by_name
from models import RetryPolicy, ScriptExecutor, Step, CompositeExecutor


class TestJobLifecycle:
    """ジョブファイルの生成→検索→更新の一連フローテスト。"""

    @pytest.mark.integration
    def test_generate_and_find(self, tmp_path):
        """生成したジョブファイルからchild_idを検索できる。"""
        repo = FileJobRepository(
            job_dir=tmp_path,
            update_script=tmp_path / "update-job.py",
        )
        steps = [
            Step(name="fetch-data", executor=ScriptExecutor(command="echo fetch"), timeout=60),
            Step(name="process-data", executor=ScriptExecutor(command="echo process"), timeout=120),
        ]

        job_file = repo.generate("lifecycle-test", "2026-05-19", steps)
        assert job_file.exists()

        # 生成されたジョブからIDを検索
        fetch_id = repo.find_child_id(job_file, "fetch-data")
        process_id = repo.find_child_id(job_file, "process-data")
        assert fetch_id != ""
        assert process_id != ""
        assert fetch_id != process_id

    @pytest.mark.integration
    def test_nested_job_structure(self, tmp_path):
        """ネストされたステップのジョブ構造が正しく生成される。"""
        repo = FileJobRepository(
            job_dir=tmp_path,
            update_script=tmp_path / "update-job.py",
        )
        child = Step(name="inner-step", executor=ScriptExecutor(command="echo inner"), timeout=30)
        parent = Step(
            name="outer-step",
            executor=CompositeExecutor(),
            steps=[child],
            timeout=60,
        )

        job_file = repo.generate("nested-test", "2026-05-19", [parent])
        data = json.loads(job_file.read_text())

        # 親ジョブの子ジョブにネスト構造がある
        outer_job = data["child_jobs"][0]
        assert outer_job["job_name"] == "outer-step"
        assert "child_jobs" in outer_job
        assert outer_job["child_jobs"][0]["job_name"] == "inner-step"

        # find_child_idでネストされたジョブも検索可能
        inner_id = repo.find_child_id(job_file, "inner-step")
        assert inner_id != ""

    @pytest.mark.integration
    def test_job_file_json_validity(self, tmp_path):
        """生成されたJSONが有効で必要なフィールドを含む。"""
        repo = FileJobRepository(
            job_dir=tmp_path,
            update_script=tmp_path / "update-job.py",
        )
        steps = [
            Step(
                name="retry-step",
                executor=ScriptExecutor(command="echo retry"),
                timeout=90,
                retry=RetryPolicy(max_attempts=3, delay=10),
            ),
        ]

        job_file = repo.generate("json-test", "2026-05-19", steps)
        data = json.loads(job_file.read_text())

        # 親ジョブの必須フィールド
        assert "job_id" in data
        assert "started_at" in data
        assert data["status"] == "running"

        # 子ジョブのリトライ情報
        child = data["child_jobs"][0]
        assert child["max_attempts"] == 3
        assert child["retry_delay"] == 10
