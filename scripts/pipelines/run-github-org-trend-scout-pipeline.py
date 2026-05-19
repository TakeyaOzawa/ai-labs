#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
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

from models import (
    AgentExecutor,
    OutputParams,
    PipelineConfig,
    PipelineContext,
    SlackParams,
    Step,
    StepParams,
)
from pipeline_engine import HOME, JST, run_pipeline


def _default_base_date() -> str:
    """基準日のデフォルト値を計算（前日）。"""
    yesterday = datetime.now(JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """GitHub org パイプラインのステップツリーを構築する。"""
    prompt = (
        f"対象日: {base_date}\n\n"
        f"環境変数GITHUB_ORG_NAMEで指定されたGitHub organizationの"
        f"{base_date}のPR活動を収集してください。"
    )

    # GITHUB_ORG_NAME 未設定チェックは ScriptExecutor で事前検証するか、
    # エージェント側で処理する。ここでは Step を定義するのみ。
    steps = [
        Step(
            name="github-org-repo-collector",
            executor=AgentExecutor(
                agent_name="github-org-repo-collector", prompt_text=prompt,
            ),
            timeout=900,
            params=StepParams(slack=SlackParams(enabled=False)),
        ),
        Step(
            name="github-org-pr-collector",
            executor=AgentExecutor(
                agent_name="github-org-pr-collector", prompt_text=prompt,
            ),
            timeout=900,
            depends_on=["github-org-repo-collector"],
            params=StepParams(slack=SlackParams(enabled=False)),
        ),
        Step(
            name="github-org-report-generator",
            executor=AgentExecutor(
                agent_name="github-org-report-generator", prompt_text=prompt,
            ),
            timeout=900,
            depends_on=["github-org-pr-collector"],
            params=StepParams(
                output=OutputParams(
                    path=f"Documents/works/scout_reports/github_org_trends/daily/{base_date}_github-org_daily.md",
                ),
                slack=SlackParams(enabled=False),
            ),
        ),
    ]
    return steps


def main() -> None:
    config = PipelineConfig(
        name="scout_daily",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)



if __name__ == "__main__":
    main()
