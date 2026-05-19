"""test_logger: lib/logger.py のテスト。"""

import logging
from pathlib import Path

import pytest

from logger import (
    JsonFormatter,
    PipelineFormatter,
    PipelineLogger,
    RotatingLineHandler,
    get_logger,
    rotate_log,
)


class TestPipelineFormatter:
    """PipelineFormatter のテスト。"""

    @pytest.mark.unit
    def test_format_info_message(self):
        formatter = PipelineFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="パイプライン起動", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "📋" in result
        assert "パイプライン起動" in result
        assert "+09:00" in result

    @pytest.mark.unit
    def test_format_error_message(self):
        formatter = PipelineFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="失敗しました", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "❌" in result

    @pytest.mark.unit
    def test_format_indented_message(self):
        formatter = PipelineFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="   ジョブファイル: /path/to/file", args=(), exc_info=None,
        )
        result = formatter.format(record)
        # インデント付きメッセージは絵文字を省略
        assert "📋" not in result
        assert "ジョブファイル" in result

    @pytest.mark.unit
    def test_format_with_name(self):
        formatter = PipelineFormatter(include_name=True)
        record = logging.LogRecord(
            name="daily", level=logging.INFO, pathname="", lineno=0,
            msg="テスト", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[daily]" in result


class TestJsonFormatter:
    """JsonFormatter のテスト。"""

    @pytest.mark.unit
    def test_format_json(self):
        import json

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="テストメッセージ", args=(), exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["level"] == "INFO"
        assert data["message"] == "テストメッセージ"
        assert "+09:00" in data["timestamp"]


class TestRotatingLineHandler:
    """RotatingLineHandler のテスト。"""

    @pytest.mark.unit
    def test_creates_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        handler = RotatingLineHandler(log_file, max_lines=10, keep_lines=5)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        handler.emit(record)
        handler.close()
        assert log_file.exists()

    @pytest.mark.unit
    def test_rotation_on_max_lines(self, tmp_path):
        log_file = tmp_path / "test.log"
        # 事前に大量の行を書き込む（1行80文字以上でファイルサイズ閾値を超えさせる）
        long_line = "x" * 100
        log_file.write_text("\n".join([long_line for _ in range(20)]) + "\n")
        handler = RotatingLineHandler(log_file, max_lines=10, keep_lines=5)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="trigger rotation", args=(), exc_info=None,
        )
        handler.emit(record)
        handler.close()
        lines = log_file.read_text().splitlines()
        # ローテーション後は keep_lines + 1（新しいレコード）以下
        assert len(lines) <= 6


class TestRotateLog:
    """rotate_log() 後方互換関数のテスト。"""

    @pytest.mark.unit
    def test_rotate_large_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("\n".join([f"line {i}" for i in range(100)]) + "\n")
        rotate_log(log_file, max_lines=50, keep_lines=10)
        lines = log_file.read_text().splitlines()
        assert len(lines) == 10

    @pytest.mark.unit
    def test_no_rotation_small_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("line 1\nline 2\n")
        rotate_log(log_file, max_lines=50, keep_lines=10)
        lines = log_file.read_text().splitlines()
        assert len(lines) == 2

    @pytest.mark.unit
    def test_nonexistent_file(self, tmp_path):
        log_file = tmp_path / "nonexistent.log"
        # Should not raise
        rotate_log(log_file, max_lines=50, keep_lines=10)


class TestPipelineLogger:
    """PipelineLogger のテスト。"""

    @pytest.mark.unit
    def test_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "logs" / "test"
        PipelineLogger("test", log_dir=log_dir)
        assert log_dir.exists()

    @pytest.mark.unit
    def test_get_agent_log_returns_path(self, tmp_path):
        plogger = PipelineLogger("test", log_dir=tmp_path)
        log_file = plogger.get_agent_log("my-agent")
        assert log_file == tmp_path / "my-agent.log"

    @pytest.mark.unit
    def test_get_notify_log_returns_path(self, tmp_path):
        plogger = PipelineLogger("test", log_dir=tmp_path)
        log_file = plogger.get_notify_log()
        assert log_file == tmp_path / "slack-notify.log"

    @pytest.mark.unit
    def test_log_error_to_stderr(self, tmp_path, capsys):
        plogger = PipelineLogger("test", log_dir=tmp_path)
        plogger.log_error("agent-x", "something failed")
        captured = capsys.readouterr()
        assert "agent-x" in captured.err
        assert "something failed" in captured.err


class TestGetLogger:
    """get_logger() のテスト。"""

    @pytest.mark.unit
    def test_returns_logger(self):
        logger = get_logger("test-unique-name-12345")
        assert isinstance(logger, logging.Logger)
        assert "test-unique-name-12345" in logger.name
