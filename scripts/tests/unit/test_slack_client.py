"""test_slack_client: lib/slack_client.py のテスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slack_client import SubprocessSlackNotifier


class TestSubprocessSlackNotifier:
    """SubprocessSlackNotifier のテスト。"""

    @pytest.mark.unit
    def test_notify_builds_correct_command(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = notifier.notify(Path("/tmp/report.md"))

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "python3.12" in call_args[0]
        assert str(notify_script) in call_args
        assert "--file" in call_args
        assert "/tmp/report.md" in call_args

    @pytest.mark.unit
    def test_notify_with_channel_and_thread(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            notifier.notify(Path("/tmp/report.md"), channel="C123", thread="ts123")

        call_args = mock_run.call_args[0][0]
        assert "--channel" in call_args
        assert "C123" in call_args
        assert "--thread" in call_args
        assert "ts123" in call_args

    @pytest.mark.unit
    def test_notify_returns_false_on_failure(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = notifier.notify(Path("/tmp/report.md"))

        assert result is False

    @pytest.mark.unit
    def test_notify_async_returns_pid(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            pid = notifier.notify_async(Path("/tmp/report.md"))

        assert pid == 12345

    @pytest.mark.unit
    def test_notify_async_returns_0_on_oserror(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("command not found")
            pid = notifier.notify_async(Path("/tmp/report.md"))

        assert pid == 0

    @pytest.mark.unit
    def test_reply_does_nothing_if_script_missing(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "nonexistent-notify-slack.py"

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.run") as mock_run:
            notifier.reply("hello", "C123", "ts456")

        mock_run.assert_not_called()

    @pytest.mark.unit
    def test_reply_calls_subprocess(self, tmp_path):
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.touch()

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        with patch("slack_client.subprocess.run") as mock_run:
            notifier.reply("hello world", "C123", "ts456")

        call_args = mock_run.call_args[0][0]
        assert "--text" in call_args
        assert "hello world" in call_args
        assert "--channel" in call_args
        assert "C123" in call_args
        assert "--thread" in call_args
        assert "ts456" in call_args
