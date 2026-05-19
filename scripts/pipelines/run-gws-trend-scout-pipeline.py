#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-gws-trend-scout-pipeline: GWSトレンドスカウト独立パイプライン

目的:
    GWSドキュメント活動の日次レポートを生成する。
    gws-trend-extractor（種別ごとの抽出・深掘り）→ gws-trend-scout（統合レポート）
    の2ステップを順次実行する。

    run-daily-pipeline.py にインライン化されているが、
    GWS単体で実行したい場合にこのスクリプトを使用する。

使い方:
    python3.12 scripts/pipelines/run-gws-trend-scout-pipeline.py [基準日]
    python3.12 scripts/pipelines/run-gws-trend-scout-pipeline.py 2026-05-19
    python3.12 scripts/pipelines/run-gws-trend-scout-pipeline.py --no-job-file

出力: Documents/works/scout_reports/gws_trends/daily/{date}_gws_daily.md
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替)
"""

from datetime import datetime, timedelta

from models import (
    AgentExecutor,
    CompositeExecutor,
    OutputParams,
    PipelineConfig,
    PipelineContext,
    SlackParams,
    Step,
    StepParams,
)
from pipeline_engine import JST, run_pipeline


def _default_base_date() -> str:
    """デフォルト基準日: 昨日。"""
    yesterday = datetime.now(tz=JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """GWSトレンドスカウトパイプラインのステップツリーを構築する。"""
    prompt = (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )

    return [
        Step(
            name="gws-trend-scout-pipeline",
            executor=CompositeExecutor(),
            timeout=1800,
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
        ),
    ]


def main() -> None:
    config = PipelineConfig(
        name="gws_trend_scout",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)


if __name__ == "__main__":
    main()
