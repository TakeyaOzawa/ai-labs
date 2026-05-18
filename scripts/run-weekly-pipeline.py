#!/usr/bin/env python3.12
"""
run-weekly-pipeline: 週次scoutパイプラインをAIコマンドで実行する（タスク管理付き）

目的:
    週次scoutパイプラインの全エージェントを順次実行し、
    digest集約→イベント収集→ブログ素材→ブログ企画を一括で行う。
    ジョブファイルベース進捗管理を行う。

使い方:
    python3.12 scripts/run-weekly-pipeline.py [基準日]
    python3.12 scripts/run-weekly-pipeline.py 2026-05-07
    python3.12 scripts/run-weekly-pipeline.py --no-job-file

出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替), python3.12 (fetch-rss-feeds.py)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from _pipeline_common import (
    HOME,
    JST,
    SCRIPTS_DIR,
    AgentExecutor,
    OutputParams,
    PipelineConfig,
    PipelineContext,
    ScriptExecutor,
    SlackParams,
    Step,
    StepParams,
    run_pipeline,
)


# ─── Weekly固有の関数 ────────────────────────────────────────────

def _default_base_date() -> str:
    """weeklyのデフォルト基準日: 当日。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d")


def _base_prompt(base_date: str) -> str:
    """共通プロンプトテキスト。"""
    return (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )


def _weekly_prompt(base_date: str) -> str:
    """週次パイプラインモード付きプロンプト。"""
    return (
        f"「週次パイプラインモード」で実行してください。"
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )


# ─── build_steps ─────────────────────────────────────────────────

def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """週次パイプラインのステップツリーを構築する。"""
    steps: list[Step] = []
    prompt = _base_prompt(base_date)
    weekly_prompt = _weekly_prompt(base_date)

    # ─── RSSフィード事前取得 ─────────────────────────────────
    rss_script = str(SCRIPTS_DIR / "fetch-rss-feeds.py")
    for category in ["tech_events", "lifestyle_events"]:
        steps.append(Step(
            name=f"rss-fetch-{category}",
            executor=ScriptExecutor(
                command=f"python3.12 {rss_script} --category {category} --date {base_date} --no-filter",
            ),
            timeout=120,
            params=StepParams(slack=SlackParams(enabled=False)),
        ))

    # ─── Digest エージェント ─────────────────────────────────
    steps.append(Step(
        name="tech-event-scout",
        executor=AgentExecutor(agent_name="tech-event-scout", prompt_text=weekly_prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/tech_events/weekly/{base_date}_tech_events.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="github-public-digest-scout",
        executor=AgentExecutor(
            agent_name="github-public-digest-scout", prompt_text=prompt,
        ),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/github_public_trends/weekly/{base_date}_github-public_weekly_digest.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="github-org-digest-scout",
        executor=AgentExecutor(
            agent_name="github-org-digest-scout", prompt_text=prompt,
        ),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/github_org_trends/weekly/{base_date}_github-org_weekly_digest.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="tech-blog-material-scout",
        executor=AgentExecutor(
            agent_name="tech-blog-material-scout", prompt_text=weekly_prompt,
        ),
        timeout=1800,
        params=StepParams(
            slack=SlackParams(enabled=False),
        ),
    ))

    steps.append(Step(
        name="github-verification-candidate-scout",
        executor=AgentExecutor(
            agent_name="github-verification-candidate-scout", prompt_text=weekly_prompt,
        ),
        timeout=900,
        params=StepParams(
            slack=SlackParams(enabled=False),
        ),
    ))

    # tech-poc-planner: 素材シートごとに個別実行
    poc_script = str(SCRIPTS_DIR / "run-poc-planner-pipeline.py")
    steps.append(Step(
        name="tech-poc-planner",
        executor=ScriptExecutor(
            command=f"python3.12 {poc_script} {base_date}",
        ),
        timeout=1200,
        depends_on=["tech-blog-material-scout"],
        params=StepParams(
            slack=SlackParams(enabled=False),
        ),
    ))

    steps.append(Step(
        name="gws-digest-scout",
        executor=AgentExecutor(agent_name="gws-digest-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/gws_trends/weekly/{base_date}_gws_weekly_digest.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="slack-digest-scout",
        executor=AgentExecutor(agent_name="slack-digest-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/slack_trends/weekly/{base_date}_slack_weekly_digest.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="notion-digest-scout",
        executor=AgentExecutor(agent_name="notion-digest-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/notion_trends/weekly/{base_date}_notion_weekly_digest.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    # ─── 参照データ鮮度チェック ──────────────────────────────
    freshness_script = str(SCRIPTS_DIR / "run-freshness-pipeline.py")
    steps.append(Step(
        name="reference-freshness-check",
        executor=ScriptExecutor(
            command=f"python3.12 {freshness_script} {base_date}",
        ),
        timeout=600,
        params=StepParams(slack=SlackParams(enabled=False)),
    ))

    return steps


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    config = PipelineConfig(
        name="scout_weekly",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
