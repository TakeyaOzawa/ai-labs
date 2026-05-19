#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-freshness-pipeline: 参照データの鮮度チェックと更新パイプライン

目的:
    Slack/Notionのユーザーディレクトリの鮮度をチェックし、
    古い場合は更新エージェントを実行する。

使い方:
    python3.12 scripts/run-freshness-pipeline.py [基準日]
    python3.12 scripts/run-freshness-pipeline.py 2026-05-17
    python3.12 scripts/run-freshness-pipeline.py --no-job-file

出力: 鮮度チェック結果 + 必要に応じてディレクトリ更新
依存: kiro-cli または claude, check-directory-freshness.py
"""

import json
import subprocess
from datetime import datetime

from models import (
    AgentExecutor,
    PipelineConfig,
    PipelineContext,
    ScriptExecutor,
    SlackParams,
    Step,
    StepParams,
)
from pipeline_engine import HOME, JST, SCRIPTS_DIR, run_pipeline


def _default_base_date() -> str:
    """デフォルト基準日: 当日。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d")


def _check_freshness(dir_type: str, max_age_days: int) -> bool:
    """鮮度チェックスクリプトを実行し、stale かどうかを返す。"""
    script = SCRIPTS_DIR / "setup" / "check-directory-freshness.py"
    result = subprocess.run(
        ["python3.12", str(script), "--type", dir_type,
         "--max-age-days", str(max_age_days)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout.strip())
        return data.get("stale", False)
    except json.JSONDecodeError:
        return False


def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """鮮度チェック結果に基づいて更新ステップを動的に生成する。"""
    steps: list[Step] = []
    prompt = "ワークフローに従って実行してください。"

    # Slack鮮度チェック
    if _check_freshness("slack", 7):
        steps.append(Step(
            name="slack-user-directory-updater",
            executor=AgentExecutor(
                agent_name="slack-user-directory-updater",
                prompt_text=prompt,
            ),
            timeout=300,
            params=StepParams(slack=SlackParams(enabled=False)),
        ))

    # Notion鮮度チェック
    if _check_freshness("notion", 14):
        steps.append(Step(
            name="notion-user-directory-updater",
            executor=AgentExecutor(
                agent_name="notion-user-directory-updater",
                prompt_text=prompt,
            ),
            timeout=300,
            params=StepParams(slack=SlackParams(enabled=False)),
        ))

    return steps


def main() -> None:
    config = PipelineConfig(
        name="freshness",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)



if __name__ == "__main__":
    main()
