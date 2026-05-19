"""テスト共通fixture・ヘルパー。"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """テスト用一時ディレクトリ。"""
    return tmp_path


@pytest.fixture
def mock_env(monkeypatch):
    """環境変数をモックするfixture。"""

    def _set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return _set_env


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """HOMEディレクトリをモックするfixture。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_slack_client():
    """SlackNotifier のモック。"""
    client = MagicMock()
    client.notify.return_value = True
    client.notify_async.return_value = 12345
    client.reply.return_value = None
    return client


@pytest.fixture
def mock_job_repository(tmp_path):
    """JobRepository のモック。"""
    repo = MagicMock()
    job_file = tmp_path / "test-job.json"
    repo.generate.return_value = job_file
    repo.update.return_value = None
    repo.find_child_id.return_value = "abc123def456"
    return repo


@pytest.fixture
def scripts_dir():
    """scriptsディレクトリのパスを返す。"""
    return Path(__file__).resolve().parent.parent
