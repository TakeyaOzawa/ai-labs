"""slack_client: ports.SlackNotifier の実装（subprocess依存）。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    from .ports import SlackNotifier
except ImportError:
    from ports import SlackNotifier


@dataclass
class SubprocessSlackNotifier:
    """notify-slack.py をsubprocessで呼び出す実装（ports.SlackNotifier準拠）。"""

    notify_script: Path
    log_file: Path

    def notify(self, file_path: Path, channel: str = "", thread: str = "") -> bool:
        """notify-slack.pyを同期実行する。"""
        cmd = [
            "python3.12",
            str(self.notify_script),
            "--file",
            str(file_path),
        ]
        if channel:
            cmd.extend(["--channel", channel])
        if thread:
            cmd.extend(["--thread", thread])
        with open(self.log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        return result.returncode == 0

    def notify_async(self, file_path: Path, channel: str = "", thread: str = "") -> int:
        """notify-slack.pyを新規プロセスで非同期に実行する（fire-and-forget）。"""
        cmd = [
            "python3.12",
            str(self.notify_script),
            "--file",
            str(file_path),
        ]
        if channel:
            cmd.extend(["--channel", channel])
        if thread:
            cmd.extend(["--thread", thread])
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            return proc.pid
        except OSError:
            return 0

    def reply(self, text: str, channel: str, thread_ts: str) -> None:
        """Slackスレッドにテキスト返信する（同期）。"""
        if not self.notify_script.exists():
            return
        cmd = [
            "python3.12",
            str(self.notify_script),
            "--text",
            text,
            "--channel",
            channel,
            "--thread",
            thread_ts,
        ]
        with open(self.log_file, "a", encoding="utf-8") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)


# 型チェック: SubprocessSlackNotifier が SlackNotifier Protocol を満たすことを確認
_: SlackNotifier = SubprocessSlackNotifier(notify_script=Path(), log_file=Path())  # type: ignore[assignment]
