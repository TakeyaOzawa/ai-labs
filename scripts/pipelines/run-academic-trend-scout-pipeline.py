#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-academic-trend-scout-pipeline: アカデミックトレンドスカウト独立パイプライン

目的:
    学術論文トレンドの日次レポートを生成する。
    academic-trend-scout エージェントを実行し、
    ビジネス・行動心理学・経済学・IT・ML・IoT分野の研究動向をサマリー化する。

    run-daily-pipeline.py にインライン化されているが、
    academic単体で実行したい場合にこのスクリプトを使用する。

使い方:
    python3.12 scripts/pipelines/run-academic-trend-scout-pipeline.py [基準日]
    python3.12 scripts/pipelines/run-academic-trend-scout-pipeline.py 2026-05-19
    python3.12 scripts/pipelines/run-academic-trend-scout-pipeline.py --no-job-file

出力: Documents/works/scout_reports/academic_trends/daily/{date}_academic_trends.md
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替)
"""

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
from pipeline_engine import JST, run_pipeline


def _default_base_date() -> str:
    """デフォルト基準日: 昨日。"""
    yesterday = datetime.now(tz=JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """アカデミックトレンドスカウトパイプラインのステップツリーを構築する。"""
    prompt = (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )

    return [
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
                slack=SlackParams(enabled=True),
            ),
        ),
    ]


def main() -> None:
    config = PipelineConfig(
        name="academic_trend_scout",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)


if __name__ == "__main__":
    main()
