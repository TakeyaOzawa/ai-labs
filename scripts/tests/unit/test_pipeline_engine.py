"""test_pipeline_engine: lib/pipeline_engine.py のテスト。"""

import pytest

from models import (
    AgentExecutor,
    InputParams,
    OutputParams,
    ScriptExecutor,
    Step,
    StepParams,
)
from pipeline_engine import build_agent_prompt_with_params, generate_id, now_jst


class TestNowJst:
    """now_jst() のテスト。"""

    @pytest.mark.unit
    def test_returns_iso_format(self):
        result = now_jst()
        assert "+09:00" in result
        assert "T" in result

    @pytest.mark.unit
    def test_returns_string(self):
        assert isinstance(now_jst(), str)


class TestGenerateId:
    """generate_id() のテスト。"""

    @pytest.mark.unit
    def test_returns_12_char_hex(self):
        id_ = generate_id()
        assert len(id_) == 12
        assert all(c in "0123456789abcdef" for c in id_)

    @pytest.mark.unit
    def test_unique_ids(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


class TestBuildAgentPromptWithParams:
    """build_agent_prompt_with_params() のテスト。"""

    @pytest.mark.unit
    def test_non_agent_executor_returns_empty(self):
        step = Step(name="test", executor=ScriptExecutor(command="echo"))
        assert build_agent_prompt_with_params(step) == ""

    @pytest.mark.unit
    def test_agent_without_params(self):
        step = Step(
            name="test",
            executor=AgentExecutor(agent_name="agent", prompt_text="do something"),
        )
        result = build_agent_prompt_with_params(step)
        assert result == "do something"

    @pytest.mark.unit
    def test_agent_with_input_params(self):
        step = Step(
            name="test",
            executor=AgentExecutor(agent_name="agent", prompt_text="analyze"),
            params=StepParams(
                input=InputParams(
                    source_type="file",
                    source_path="/tmp/input.md",
                ),
            ),
        )
        result = build_agent_prompt_with_params(step)
        assert "---" in result
        assert "agent_params:" in result
        assert "source_type: file" in result
        assert 'source_path: "/tmp/input.md"' in result
        assert "analyze" in result

    @pytest.mark.unit
    def test_agent_with_output_params(self):
        step = Step(
            name="test",
            executor=AgentExecutor(agent_name="agent", prompt_text="generate"),
            params=StepParams(
                output=OutputParams(
                    enabled=True,
                    path="/tmp/output.md",
                ),
            ),
        )
        result = build_agent_prompt_with_params(step)
        assert "enabled: true" in result
        assert 'path: "/tmp/output.md"' in result

    @pytest.mark.unit
    def test_agent_with_input_and_output(self):
        step = Step(
            name="test",
            executor=AgentExecutor(agent_name="agent", prompt_text="transform"),
            params=StepParams(
                input=InputParams(source_type="theme", source_theme="AI trends"),
                output=OutputParams(path="/tmp/report.md"),
            ),
        )
        result = build_agent_prompt_with_params(step)
        assert "input:" in result
        assert "output:" in result
        assert 'source_theme: "AI trends"' in result
        assert "transform" in result

    @pytest.mark.unit
    def test_agent_with_url_source(self):
        step = Step(
            name="test",
            executor=AgentExecutor(agent_name="agent", prompt_text="fetch"),
            params=StepParams(
                input=InputParams(
                    source_type="url",
                    source_url="https://example.com/feed.xml",
                ),
            ),
        )
        result = build_agent_prompt_with_params(step)
        assert 'source_url: "https://example.com/feed.xml"' in result
