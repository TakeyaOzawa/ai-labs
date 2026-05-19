"""test_gws_client: lib/gws_client.py のテスト。"""

from pathlib import Path

import pytest

from gws_client import GWSClient, GWSConfig


class TestGWSConfig:
    """GWSConfig のテスト。"""

    @pytest.mark.unit
    def test_default_values(self):
        config = GWSConfig()
        assert "credentials.json" in str(config.credentials_path)
        assert "token.json" in str(config.token_path)
        assert config.scopes == []

    @pytest.mark.unit
    def test_custom_values(self, tmp_path):
        config = GWSConfig(
            credentials_path=tmp_path / "creds.json",
            token_path=tmp_path / "token.json",
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        assert config.credentials_path == tmp_path / "creds.json"
        assert len(config.scopes) == 1


class TestGWSClient:
    """GWSClient のテスト。"""

    @pytest.mark.unit
    def test_authenticate_returns_false_if_no_credentials(self, tmp_path):
        config = GWSConfig(credentials_path=tmp_path / "nonexistent.json")
        client = GWSClient(config=config)
        assert client.authenticate() is False

    @pytest.mark.unit
    def test_authenticate_returns_true_if_credentials_exist(self, tmp_path):
        creds = tmp_path / "credentials.json"
        creds.write_text("{}")
        config = GWSConfig(credentials_path=creds)
        client = GWSClient(config=config)
        assert client.authenticate() is True

    @pytest.mark.unit
    def test_default_config(self):
        client = GWSClient()
        assert client.config is not None
