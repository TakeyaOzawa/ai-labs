"""test_job_manager: lib/job_manager.py のテスト。"""

import json
from pathlib import Path

import pytest

from job_manager import FileJobRepository, _find_job_id_by_name, _generate_id, _step_to_job
from models import RetryPolicy, ScriptExecutor, Step, CompositeExecutor


class TestGenerateId:
    """_generate_id() のテスト。"""

    @pytest.mark.unit
    def test_returns_12_char_hex(self):
        id_ = _generate_id()
        assert len(id_) == 12
        assert all(c in "0123456789abcdef" for c in id_)


class TestStepToJob:
    """_step_to_job() のテスト。"""

    @pytest.mark.unit
    def test_simple_step(self):
        step = Step(name="test-step", executor=ScriptExecutor(command="echo"))
        job = _step_to_job(step)
        assert job["job_name"] == "test-step"
        assert job["status"] == "pending"
        assert job["timeout"] == 300
        assert "job_id" in job
        assert len(job["job_id"]) == 12

    @pytest.mark.unit
    def test_step_with_retry(self):
        step = Step(
            name="retry-step",
            executor=ScriptExecutor(command="echo"),
            retry=RetryPolicy(max_attempts=3, delay=60),
        )
        job = _step_to_job(step)
        assert job["retry_delay"] == 60
        assert job["max_attempts"] == 3

    @pytest.mark.unit
    def test_step_with_depends_on(self):
        step = Step(
            name="dep-step",
            executor=ScriptExecutor(command="echo"),
            depends_on=["step-a"],
        )
        job = _step_to_job(step)
        assert job["depends_on"] == ["step-a"]

    @pytest.mark.unit
    def test_nested_steps(self):
        child = Step(name="child", executor=ScriptExecutor(command="echo"))
        parent = Step(
            name="parent",
            executor=CompositeExecutor(),
            steps=[child],
        )
        job = _step_to_job(parent)
        assert "child_jobs" in job
        assert len(job["child_jobs"]) == 1
        assert job["child_jobs"][0]["job_name"] == "child"


class TestFindJobIdByName:
    """_find_job_id_by_name() のテスト。"""

    @pytest.mark.unit
    def test_finds_top_level(self):
        jobs = [
            {"job_id": "aaa111", "job_name": "step-a"},
            {"job_id": "bbb222", "job_name": "step-b"},
        ]
        assert _find_job_id_by_name(jobs, "step-a") == "aaa111"
        assert _find_job_id_by_name(jobs, "step-b") == "bbb222"

    @pytest.mark.unit
    def test_finds_nested(self):
        jobs = [
            {
                "job_id": "parent1",
                "job_name": "parent",
                "child_jobs": [
                    {"job_id": "child1", "job_name": "nested-step"},
                ],
            },
        ]
        assert _find_job_id_by_name(jobs, "nested-step") == "child1"

    @pytest.mark.unit
    def test_returns_empty_for_missing(self):
        jobs = [{"job_id": "aaa", "job_name": "step-a"}]
        assert _find_job_id_by_name(jobs, "nonexistent") == ""

    @pytest.mark.unit
    def test_empty_list(self):
        assert _find_job_id_by_name([], "anything") == ""


class TestFileJobRepository:
    """FileJobRepository のテスト。"""

    @pytest.mark.unit
    def test_generate_creates_file(self, tmp_path):
        repo = FileJobRepository(
            job_dir=tmp_path / "jobs",
            update_script=tmp_path / "update-job.py",
        )
        steps = [
            Step(name="step-1", executor=ScriptExecutor(command="echo 1"), timeout=60),
            Step(name="step-2", executor=ScriptExecutor(command="echo 2"), timeout=120),
        ]
        job_file = repo.generate("test-pipeline", "2026-05-19", steps)
        assert job_file.exists()
        assert job_file.name == "2026-05-19_test-pipeline.json"

    @pytest.mark.unit
    def test_generate_json_structure(self, tmp_path):
        repo = FileJobRepository(
            job_dir=tmp_path / "jobs",
            update_script=tmp_path / "update-job.py",
        )
        steps = [
            Step(name="step-1", executor=ScriptExecutor(command="echo"), timeout=100),
        ]
        job_file = repo.generate("my-pipeline", "2026-05-19", steps)
        data = json.loads(job_file.read_text())
        assert data["job_name"] == "my-pipeline"
        assert data["base_date"] == "2026-05-19"
        assert data["status"] == "running"
        assert data["timeout"] == 100
        assert len(data["child_jobs"]) == 1
        assert data["child_jobs"][0]["job_name"] == "step-1"

    @pytest.mark.unit
    def test_find_child_id(self, tmp_path):
        repo = FileJobRepository(
            job_dir=tmp_path,
            update_script=tmp_path / "update-job.py",
        )
        job_data = {
            "job_id": "parent123",
            "job_name": "pipeline",
            "child_jobs": [
                {"job_id": "child_aaa", "job_name": "step-a"},
                {"job_id": "child_bbb", "job_name": "step-b"},
            ],
        }
        job_file = tmp_path / "test-job.json"
        job_file.write_text(json.dumps(job_data))
        assert repo.find_child_id(job_file, "step-a") == "child_aaa"
        assert repo.find_child_id(job_file, "step-b") == "child_bbb"
        assert repo.find_child_id(job_file, "nonexistent") == ""
