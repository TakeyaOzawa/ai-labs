"""test_models: lib/models.py のdataclass生成テスト。"""

import pytest

from models import (
    AgentExecutor,
    CompositeExecutor,
    ExecutionContext,
    Executor,
    InputParams,
    JobParams,
    LogParams,
    OutputParams,
    PipelineConfig,
    PipelineContext,
    RetryPolicy,
    ScriptExecutor,
    SlackParams,
    Step,
    StepParams,
)


class TestRetryPolicy:
    """RetryPolicy のテスト。"""

    @pytest.mark.unit
    def test_default_values(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 1
        assert policy.delay == 30
        assert policy.backoff == "fixed"

    @pytest.mark.unit
    def test_custom_values(self):
        policy = RetryPolicy(max_attempts=3, delay=60, backoff="exponential")
        assert policy.max_attempts == 3
        assert policy.delay == 60
        assert policy.backoff == "exponential"


class TestExecutors:
    """Executor 種別のテスト。"""

    @pytest.mark.unit
    def test_base_executor(self):
        ex = Executor()
        assert ex.type == ""

    @pytest.mark.unit
    def test_agent_executor(self):
        ex = AgentExecutor(agent_name="test-agent", prompt_text="do something")
        assert ex.type == "agent"
        assert ex.agent_name == "test-agent"
        assert ex.prompt_text == "do something"

    @pytest.mark.unit
    def test_script_executor(self):
        ex = ScriptExecutor(command="python3.12 test.py", env={"KEY": "val"})
        assert ex.type == "script"
        assert ex.command == "python3.12 test.py"
        assert ex.env == {"KEY": "val"}

    @pytest.mark.unit
    def test_script_executor_no_env(self):
        ex = ScriptExecutor(command="echo hello")
        assert ex.env is None

    @pytest.mark.unit
    def test_composite_executor(self):
        ex = CompositeExecutor()
        assert ex.type == "composite"


class TestStepParams:
    """StepParams のテスト。"""

    @pytest.mark.unit
    def test_input_params_defaults(self):
        inp = InputParams()
        assert inp.source_type == "none"
        assert inp.source_path == ""

    @pytest.mark.unit
    def test_output_params_defaults(self):
        out = OutputParams()
        assert out.enabled is True
        assert out.path == ""

    @pytest.mark.unit
    def test_slack_params_defaults(self):
        slack = SlackParams()
        assert slack.enabled is True
        assert slack.channel == ""
        assert slack.thread_mode == "compact"

    @pytest.mark.unit
    def test_job_params_defaults(self):
        job = JobParams()
        assert job.enabled is False

    @pytest.mark.unit
    def test_step_params_all_none(self):
        params = StepParams()
        assert params.input is None
        assert params.output is None
        assert params.log is None
        assert params.slack is None
        assert params.job is None

    @pytest.mark.unit
    def test_step_params_with_values(self):
        params = StepParams(
            input=InputParams(source_type="file", source_path="/tmp/test.md"),
            output=OutputParams(path="/tmp/out.md"),
        )
        assert params.input.source_type == "file"
        assert params.output.path == "/tmp/out.md"


class TestStep:
    """Step のテスト。"""

    @pytest.mark.unit
    def test_minimal_step(self):
        step = Step(name="test-step", executor=ScriptExecutor(command="echo hi"))
        assert step.name == "test-step"
        assert step.mode == "sync"
        assert step.timeout == 300
        assert step.retry is None
        assert step.depends_on is None
        assert step.params is None
        assert step.steps is None

    @pytest.mark.unit
    def test_step_with_retry(self):
        step = Step(
            name="retry-step",
            executor=AgentExecutor(agent_name="agent"),
            retry=RetryPolicy(max_attempts=3, delay=10),
        )
        assert step.retry.max_attempts == 3
        assert step.retry.delay == 10

    @pytest.mark.unit
    def test_nested_steps(self):
        child = Step(name="child", executor=ScriptExecutor(command="echo child"))
        parent = Step(
            name="parent",
            executor=CompositeExecutor(),
            steps=[child],
        )
        assert len(parent.steps) == 1
        assert parent.steps[0].name == "child"

    @pytest.mark.unit
    def test_step_with_depends_on(self):
        step = Step(
            name="dependent",
            executor=ScriptExecutor(command="echo dep"),
            depends_on=["step-a", "step-b"],
        )
        assert step.depends_on == ["step-a", "step-b"]


class TestPipelineContext:
    """PipelineContext のテスト。"""

    @pytest.mark.unit
    def test_defaults(self, tmp_path):
        ctx = PipelineContext(
            base_date="2026-05-19",
            log_dir=tmp_path,
            use_job_file=True,
        )
        assert ctx.base_date == "2026-05-19"
        assert ctx.slack_channel == ""
        assert ctx.slack_thread_ts == ""


class TestExecutionContext:
    """ExecutionContext のテスト。"""

    @pytest.mark.unit
    def test_defaults(self):
        ctx = ExecutionContext(
            job_file=None,
            use_job_file=False,
            base_date="2026-05-19",
            plogger=None,
        )
        assert ctx.completed_names == set()
        assert ctx.slack_channel == ""
