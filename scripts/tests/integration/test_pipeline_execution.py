"""test_pipeline_execution: パイプライン実行の結合テスト。"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from models import (
    CompositeExecutor,
    ExecutionContext,
    ScriptExecutor,
    Step,
    RetryPolicy,
)
from pipeline_engine import execute_steps, generate_job_file


class TestExecuteStepsIntegration:
    """execute_steps() の結合テスト。"""

    @pytest.mark.integration
    def test_single_script_step_success(self, tmp_path):
        """最小構成のパイプライン（ScriptExecutor 1ステップ）のE2E実行テスト。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        plogger = MagicMock()
        plogger.get_agent_log.return_value = log_dir / "test.log"
        plogger.get_notify_log.return_value = log_dir / "notify.log"

        step = Step(
            name="echo-test",
            executor=ScriptExecutor(command="echo hello"),
            timeout=10,
        )

        context = ExecutionContext(
            job_file=None,
            use_job_file=False,
            base_date="2026-05-19",
            plogger=plogger,
        )

        success, failed, skipped = execute_steps([step], context)
        assert success == 1
        assert failed == 0
        assert skipped == 0
        assert "echo-test" in context.completed_names

    @pytest.mark.integration
    def test_script_step_failure(self, tmp_path):
        """失敗するスクリプトステップのテスト。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # 失敗するスクリプトを作成
        fail_script = tmp_path / "fail.sh"
        fail_script.write_text("#!/bin/bash\nexit 1\n")
        fail_script.chmod(0o755)

        plogger = MagicMock()
        plogger.get_agent_log.return_value = log_dir / "test.log"

        step = Step(
            name="fail-test",
            executor=ScriptExecutor(command=str(fail_script)),
            timeout=10,
        )

        context = ExecutionContext(
            job_file=None,
            use_job_file=False,
            base_date="2026-05-19",
            plogger=plogger,
        )

        success, failed, skipped = execute_steps([step], context)
        assert success == 0
        assert failed == 1

    @pytest.mark.integration
    def test_dependency_skip(self, tmp_path):
        """依存関係未完了時のスキップテスト。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        plogger = MagicMock()
        plogger.get_agent_log.return_value = log_dir / "test.log"

        step = Step(
            name="dependent-step",
            executor=ScriptExecutor(command="echo should-not-run"),
            depends_on=["missing-step"],
        )

        context = ExecutionContext(
            job_file=None,
            use_job_file=False,
            base_date="2026-05-19",
            plogger=plogger,
        )

        success, failed, skipped = execute_steps([step], context)
        assert skipped == 1
        assert success == 0
        assert failed == 0

    @pytest.mark.integration
    def test_composite_executor(self, tmp_path):
        """CompositeExecutor のネスト実行テスト。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        plogger = MagicMock()
        plogger.get_agent_log.return_value = log_dir / "test.log"

        child1 = Step(name="child-1", executor=ScriptExecutor(command="echo c1"), timeout=10)
        child2 = Step(name="child-2", executor=ScriptExecutor(command="echo c2"), timeout=10)
        parent = Step(
            name="parent",
            executor=CompositeExecutor(),
            steps=[child1, child2],
        )

        context = ExecutionContext(
            job_file=None,
            use_job_file=False,
            base_date="2026-05-19",
            plogger=plogger,
        )

        success, failed, skipped = execute_steps([parent], context)
        assert success == 1
        assert failed == 0


class TestGenerateJobFileIntegration:
    """generate_job_file() の結合テスト。"""

    @pytest.mark.integration
    def test_generates_valid_json(self, tmp_path, monkeypatch):
        """ジョブファイル生成→JSON構造の検証。"""
        monkeypatch.setattr("pipeline_engine.HOME", tmp_path)
        job_dir = tmp_path / "Documents" / "works" / "jobs"

        steps = [
            Step(name="step-a", executor=ScriptExecutor(command="echo a"), timeout=60),
            Step(name="step-b", executor=ScriptExecutor(command="echo b"), timeout=120),
        ]

        job_file = generate_job_file("test-pipeline", "2026-05-19", steps)
        assert job_file.exists()

        data = json.loads(job_file.read_text())
        assert data["job_name"] == "test-pipeline"
        assert data["base_date"] == "2026-05-19"
        assert data["status"] == "running"
        assert len(data["child_jobs"]) == 2
        assert data["child_jobs"][0]["job_name"] == "step-a"
        assert data["child_jobs"][1]["job_name"] == "step-b"
        assert data["timeout"] == 180
