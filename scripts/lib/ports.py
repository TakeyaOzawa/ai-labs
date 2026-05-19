"""ports: 外部依存に対するProtocol定義（インターフェース集約）。

外部依存ゼロ（標準ライブラリの typing.Protocol のみ使用）。
テスト時のモック定義はこのファイルのProtocolを参照する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SlackNotifier(Protocol):
    """Slack通知のインターフェース。"""

    def notify(self, file_path: Path, channel: str = "", thread: str = "") -> bool:
        """ファイルをSlackに同期通知する。"""
        ...

    def notify_async(self, file_path: Path, channel: str = "", thread: str = "") -> int:
        """ファイルをSlackに非同期通知する。PIDを返す。"""
        ...

    def reply(self, text: str, channel: str, thread_ts: str) -> None:
        """Slackスレッドにテキスト返信する。"""
        ...


class JobRepository(Protocol):
    """ジョブファイルのCRUD操作インターフェース。"""

    def generate(self, pipeline_name: str, base_date: str, steps: list) -> Path:
        """Step ツリーからジョブファイルを自動生成する。"""
        ...

    def update(self, job_file: Path, job_id: str, updates: dict) -> None:
        """ジョブを更新する。"""
        ...

    def find_child_id(self, job_file: Path, job_name: str) -> str:
        """ジョブファイルから指定ジョブ名のIDを再帰検索で取得する。"""
        ...


class CommandRunner(Protocol):
    """外部コマンド実行のインターフェース。"""

    def run(self, cmd: list[str], log_file: Path, timeout: int = 0) -> tuple[bool, str]:
        """コマンドを実行し、(成功フラグ, 詳細理由) を返す。"""
        ...
