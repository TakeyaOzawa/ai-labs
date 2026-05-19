"""test_config: lib/config.py のテスト。"""

from pathlib import Path

import pytest

from config import ScriptsConfig


class TestScriptsConfig:
    """ScriptsConfig のテスト。"""

    @pytest.mark.unit
    def test_default_values(self):
        config = ScriptsConfig()
        assert config.home == Path.home()
        assert config.scripts_dir.exists()
        assert "logs" in str(config.log_base_dir)
        assert "jobs" in str(config.job_base_dir)

    @pytest.mark.unit
    def test_frozen(self):
        config = ScriptsConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.home = Path("/tmp")  # type: ignore[misc]

    @pytest.mark.unit
    def test_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SCOUT_HOME", str(tmp_path))
        monkeypatch.setenv("SCOUT_LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setenv("SCOUT_JOB_DIR", str(tmp_path / "jobs"))
        config = ScriptsConfig.from_env()
        assert config.home == tmp_path
        assert config.log_base_dir == tmp_path / "logs"
        assert config.job_base_dir == tmp_path / "jobs"

    @pytest.mark.unit
    def test_from_env_defaults(self, monkeypatch):
        # 環境変数未設定時はデフォルト値
        monkeypatch.delenv("SCOUT_HOME", raising=False)
        monkeypatch.delenv("SCOUT_LOG_DIR", raising=False)
        monkeypatch.delenv("SCOUT_JOB_DIR", raising=False)
        config = ScriptsConfig.from_env()
        assert config.home == Path.home()

    @pytest.mark.unit
    def test_platform_cmd(self):
        config = ScriptsConfig()
        assert config.platform_cmd.name == "platform-commands.sh"

    @pytest.mark.unit
    def test_resolve_script(self):
        config = ScriptsConfig()
        path = config.resolve_script("slack", "notify-slack.py")
        assert path == config.scripts_dir / "slack" / "notify-slack.py"
