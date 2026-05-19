"""test_slack_dispatch_flow: Slack通知フローの結合テスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slack_client import SubprocessSlackNotifier


class TestSlackDispatchFlow:
    """Slack通知の一連フローテスト。"""

    @pytest.mark.integration
    def test_notify_creates_log_entry(self, tmp_path):
        """通知実行時にログファイルにエントリが追加される。"""
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.write_text("#!/usr/bin/env python3.12\nimport sys; sys.exit(0)")
        notify_script.chmod(0o755)

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        report = tmp_path / "report.md"
        report.write_text("# Test Report\n\nContent here.")

        with patch("slack_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = notifier.notify(report, channel="C123")

        assert result is True

    @pytest.mark.integration
    def test_async_notify_fire_and_forget(self, tmp_path):
        """非同期通知がPIDを返してfire-and-forgetで動作する。"""
        log_file = tmp_path / "notify.log"
        log_file.touch()
        notify_script = tmp_path / "notify-slack.py"
        notify_script.write_text("#!/usr/bin/env python3.12\nimport sys; sys.exit(0)")
        notify_script.chmod(0o755)

        notifier = SubprocessSlackNotifier(
            notify_script=notify_script,
            log_file=log_file,
        )

        report = tmp_path / "report.md"
        report.write_text("# Async Report")

        with patch("slack_client.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=99999)
            pid = notifier.notify_async(report, channel="C456", thread="compact")

        assert pid == 99999
        # Popenが正しい引数で呼ばれたことを確認
        call_args = mock_popen.call_args[0][0]
        assert "--channel" in call_args
        assert "C456" in call_args
        assert "--thread" in call_args
        assert "compact" in call_args
