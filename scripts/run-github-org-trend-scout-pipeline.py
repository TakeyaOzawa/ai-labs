#!/usr/bin/env python3.12
"""
run-github-org-trend-scout-pipeline: GitHub org日次トレンドスカウトパイプライン

目的:
    github-org-trend-scoutを複数エージェントに分割してパイプライン実行し、
    コンテキスト逼迫問題を解決する。

使い方:
    python3.12 scripts/run-github-org-trend-scout-pipeline.py [基準日]
    python3.12 scripts/run-github-org-trend-scout-pipeline.py 2026-05-14
    python3.12 scripts/run-github-org-trend-scout-pipeline.py --no-job-file

出力: GitHub org日次レポート
依存: kiro-cli または claude, GITHUB_ORG_NAME環境変数
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from _pipeline_common import (
    HOME,
    JST,
    PipelineConfig,
    now_jst,
    run_pipeline,
)

# ─── パイプライン設定 ────────────────────────────────────────────

AGENTS = [
    "github-org-repo-collector",
    "github-org-pr-collector", 
    "github-org-report-generator"
]

NOTIFY_FILE_MAP = {}  # Slack通知不要

def _default_base_date() -> str:
    """基準日のデフォルト値を計算（前日）。"""
    yesterday = datetime.now(JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def _rss_fetch_hook(base_date: str, scripts_dir: Path) -> None:
    """RSS事前取得（不要）。"""
    return None

def _build_prompt(agent: str, base_date: str) -> str:
    """エージェント実行プロンプト構築。"""
    return f"対象日: {base_date}\n\n環境変数GITHUB_ORG_NAMEで指定されたGitHub organizationの{base_date}のPR活動を収集してください。"

def _resolve_notify_path(agent: str, base_date: str) -> None:
    """通知ファイルパス動的解決（不要）。"""
    return None

def _pre_agent_hook(agent: str, base_date: str) -> tuple[str, bool] | str | None:
    """エージェント実行前チェック。"""
    if not os.getenv("GITHUB_ORG_NAME"):
        return ("環境変数 GITHUB_ORG_NAME が未設定です", False)
    return None

def _post_agents_hook(base_date: str) -> None:
    """全エージェント実行後の追加ステップ（不要）。"""
    return None

def _post_notify_hook(base_date: str) -> None:
    """通知後の追加ステップ（不要）。"""
    return None

# ─── メイン実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    config = PipelineConfig(
        name="github-org-trend-scout-pipeline",
        log_dir=HOME / "logs/jobs/scout_daily",
        agents=AGENTS,
        notify_file_map=NOTIFY_FILE_MAP,
        create_jobs_script="create-jobs.py --pipeline github-org-trend-scout-pipeline",
        default_base_date=_default_base_date,
        rss_fetch_hook=_rss_fetch_hook,
        build_prompt=_build_prompt,
        resolve_notify_path=_resolve_notify_path,
        pre_agent_hook=_pre_agent_hook,
        post_agents_hook=_post_agents_hook,
        post_notify_hook=_post_notify_hook,
    )
    
    run_pipeline(config)