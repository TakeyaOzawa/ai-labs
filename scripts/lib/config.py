"""config: 設定・定数の一元管理。"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class ScriptsConfig:
    """スクリプト実行環境の設定。"""

    home: Path = field(default_factory=Path.home)
    scripts_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    log_base_dir: Path = field(default_factory=lambda: Path.home() / "logs" / "jobs")
    job_base_dir: Path = field(
        default_factory=lambda: Path.home() / "Documents" / "works" / "jobs"
    )

    @classmethod
    def from_env(cls) -> ScriptsConfig:
        """環境変数からオーバーライド可能な設定を生成。"""
        home = Path(os.environ.get("SCOUT_HOME", str(Path.home())))
        scripts_dir = Path(
            os.environ.get("SCOUT_SCRIPTS_DIR", str(Path(__file__).resolve().parent.parent))
        )
        log_base_dir = Path(os.environ.get("SCOUT_LOG_DIR", str(home / "logs" / "jobs")))
        job_base_dir = Path(
            os.environ.get("SCOUT_JOB_DIR", str(home / "Documents" / "works" / "jobs"))
        )
        return cls(
            home=home,
            scripts_dir=scripts_dir,
            log_base_dir=log_base_dir,
            job_base_dir=job_base_dir,
        )

    @property
    def platform_cmd(self) -> Path:
        """platform-commands.sh のパス。"""
        return self.scripts_dir / "platform-commands.sh"

    def resolve_script(self, subdir: str, name: str) -> Path:
        """サブディレクトリ内のスクリプトパスを解決する。"""
        return self.scripts_dir / subdir / name


def load_env(platform_cmd: Path | None = None) -> None:
    """環境変数をロードする（launchd環境対応）。"""
    if os.environ.get("MY_SLACK_OAUTH_TOKEN"):
        return
    if platform_cmd is None:
        platform_cmd = Path(__file__).resolve().parent.parent / "platform-commands.sh"
    result = subprocess.run(
        [str(platform_cmd), "source-env"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ[key] = value
