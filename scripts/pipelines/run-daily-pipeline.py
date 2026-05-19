#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-daily-pipeline: 日次scoutパイプラインをAIコマンドで実行する（タスク管理付き）

目的:
    日次scoutパイプラインの全エージェントを順次実行し、
    RSSフィード取得→各scout実行→結果サマリー出力を一括で行う。
    ジョブファイルベース進捗管理を行う。

使い方:
    python3.12 scripts/run-daily-pipeline.py [基準日]
    python3.12 scripts/run-daily-pipeline.py 2026-05-07
    python3.12 scripts/run-daily-pipeline.py --no-job-file

出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替), python3.12 (fetch-rss-feeds.py)
"""

from datetime import datetime, timedelta

from models import (
    AgentExecutor,
    CompositeExecutor,
    OutputParams,
    PipelineConfig,
    PipelineContext,
    ScriptExecutor,
    SlackParams,
    Step,
    StepParams,
)
from pipeline_engine import HOME, JST, SCRIPTS_DIR, run_pipeline

# ─── Daily固有の定数 ─────────────────────────────────────────────

# lifestyle-event-scoutは曜日によって出力ファイル名が変わる
LIFESTYLE_THEME_MAP: dict[int, str] = {
    0: "outing",       # 月曜日
    1: "experience",   # 火曜日
    2: "culture",      # 水曜日
    3: "learning",     # 木曜日
    4: "food-living",  # 金曜日
    5: "money-life",   # 土曜日
    # 6: 日曜日 = 週次サマリー（weekly/に出力）
}


# ─── Daily固有の関数 ─────────────────────────────────────────────

def _default_base_date() -> str:
    """dailyのデフォルト基準日: 昨日。"""
    yesterday = datetime.now(tz=JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _resolve_lifestyle_output(today_date: str) -> str:
    """lifestyle-event-scoutの出力パスを曜日テーマで動的解決する。"""
    target_date = datetime.now(tz=JST)
    weekday = target_date.weekday()
    theme = LIFESTYLE_THEME_MAP.get(weekday)
    if theme is None:
        # 日曜日: 週次サマリー
        return f"Documents/works/scout_reports/lifestyle_events/weekly/{today_date}_lifestyle_weekly_summary.md"
    return f"Documents/works/scout_reports/lifestyle_events/daily/{today_date}_lifestyle_{theme}.md"


def _base_prompt(base_date: str) -> str:
    """共通プロンプトテキスト。"""
    return (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )


# ─── build_steps ─────────────────────────────────────────────────

def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """日次パイプラインのステップツリーを構築する。"""
    today_date = datetime.now(tz=JST).strftime("%Y-%m-%d")
    steps: list[Step] = []

    # ─── Pre-pipeline: claude agent定義同期 ──────────────────
    steps.append(Step(
        name="sync-claude-agents",
        executor=ScriptExecutor(
            command=f"python3.12 {SCRIPTS_DIR / 'ai' / 'sync-claude-agents.py'}",
        ),
        timeout=60,
        params=StepParams(slack=SlackParams(enabled=False)),
    ))

    # ─── RSSフィード事前取得 ─────────────────────────────────
    rss_script = str(SCRIPTS_DIR / "rss" / "fetch-rss-feeds.py")
    for category in ["tech", "biz_car", "academic", "lifestyle_events"]:
        feed_date = today_date if category == "lifestyle_events" else base_date
        steps.append(Step(
            name=f"rss-fetch-{category}",
            executor=ScriptExecutor(
                command=f"python3.12 {rss_script} --category {category} --date {feed_date}",
            ),
            timeout=120,
            params=StepParams(slack=SlackParams(enabled=False)),
        ))

    # ─── Scout エージェント ──────────────────────────────────
    prompt = _base_prompt(base_date)

    steps.append(Step(
        name="tech-trend-scout",
        executor=AgentExecutor(agent_name="tech-trend-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/tech_trends/daily/{base_date}_tech_trends.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="biz-car-trend-scout",
        executor=AgentExecutor(agent_name="biz-car-trend-scout", prompt_text=prompt),
        timeout=1200,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/biz_car_trends/daily/{base_date}_biz_car_trends.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    # academic-trend-scout-pipeline（CompositeExecutor でインライン化）
    steps.append(Step(
        name="academic-trend-scout-pipeline",
        executor=CompositeExecutor(),
        timeout=1200,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/academic_trends/daily/{base_date}_academic_trends.md",
            ),
            slack=SlackParams(enabled=True),
        ),
        steps=[
            Step(
                name="academic-trend-scout",
                executor=AgentExecutor(
                    agent_name="academic-trend-scout", prompt_text=prompt,
                ),
                timeout=1200,
                params=StepParams(
                    output=OutputParams(
                        path=f"Documents/works/scout_reports/academic_trends/daily/{base_date}_academic_trends.md",
                    ),
                    slack=SlackParams(enabled=False),
                ),
            ),
        ],
    ))

    # lifestyle-event-scout（当日基準）
    lifestyle_prompt = _base_prompt(today_date)
    lifestyle_output = _resolve_lifestyle_output(today_date)
    steps.append(Step(
        name="lifestyle-event-scout",
        executor=AgentExecutor(
            agent_name="lifestyle-event-scout", prompt_text=lifestyle_prompt,
        ),
        timeout=900,
        params=StepParams(
            output=OutputParams(path=lifestyle_output),
            slack=SlackParams(enabled=True),
        ),
    ))

    rss_updater_script = str(SCRIPTS_DIR / "rss" / "rss-source-updater.py")
    steps.append(Step(
        name="rss-source-updater",
        executor=ScriptExecutor(
            command=f"python3.12 {rss_updater_script} --date {base_date}",
        ),
        timeout=180,
        params=StepParams(slack=SlackParams(enabled=False)),
    ))

    steps.append(Step(
        name="github-public-trend-scout",
        executor=AgentExecutor(
            agent_name="github-public-trend-scout", prompt_text=prompt,
        ),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/github_public_trends/daily/{base_date}_github-public_daily.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    # github-org-trend-scout-pipeline（CompositeExecutor でインライン化）
    steps.append(Step(
        name="github-org-trend-scout",
        executor=AgentExecutor(
            agent_name="github-org-trend-scout", prompt_text=prompt,
        ),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/github_org_trends/daily/{base_date}_github-org_daily.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    # gws-trend-scout-pipeline（CompositeExecutor でインライン化）
    steps.append(Step(
        name="gws-trend-scout-pipeline",
        executor=CompositeExecutor(),
        timeout=600,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/gws_trends/daily/{base_date}_gws_daily.md",
            ),
            slack=SlackParams(enabled=True),
        ),
        steps=[
            Step(
                name="gws-trend-extractor",
                executor=AgentExecutor(
                    agent_name="gws-trend-extractor", prompt_text=prompt,
                ),
                timeout=900,
                params=StepParams(slack=SlackParams(enabled=False)),
            ),
            Step(
                name="gws-trend-report",
                executor=AgentExecutor(
                    agent_name="gws-trend-scout", prompt_text=prompt,
                ),
                timeout=900,
                depends_on=["gws-trend-extractor"],
                params=StepParams(
                    output=OutputParams(
                        path=f"Documents/works/scout_reports/gws_trends/daily/{base_date}_gws_daily.md",
                    ),
                    slack=SlackParams(enabled=False),
                ),
            ),
        ],
    ))

    steps.append(Step(
        name="slack-trend-scout",
        executor=AgentExecutor(agent_name="slack-trend-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/slack_trends/daily/{base_date}_slack_daily.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    steps.append(Step(
        name="notion-trend-scout",
        executor=AgentExecutor(agent_name="notion-trend-scout", prompt_text=prompt),
        timeout=900,
        params=StepParams(
            output=OutputParams(
                path=f"Documents/works/scout_reports/notion_trends/daily/{base_date}_notion_daily.md",
            ),
            slack=SlackParams(enabled=True),
        ),
    ))

    return steps


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    config = PipelineConfig(
        name="scout_daily",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)



if __name__ == "__main__":
    main()
