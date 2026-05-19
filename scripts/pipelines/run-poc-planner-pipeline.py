#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-poc-planner-pipeline: tech-poc-planner を素材シート1件ごとに個別実行するパイプライン

目的:
    tech-blog-material-scout が生成した素材シートを列挙し、
    各シートに対して tech-poc-planner を個別実行する。

使い方:
    python3.12 scripts/run-poc-planner-pipeline.py [基準日]
    python3.12 scripts/run-poc-planner-pipeline.py 2026-05-17
    python3.12 scripts/run-poc-planner-pipeline.py --no-job-file

出力: 各素材シートに対応するPoC計画ファイル
依存: kiro-cli または claude
"""

import time
from datetime import datetime

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
    """デフォルト基準日: 当日。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d")


def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    """素材シートを列挙し、各シートに対する Step を動的に生成する。"""
    material_dir = (HOME / "Documents" / "works" /
                    "scout_reports" / "tech_blog_materials" / "weekly")

    # ファイルシステムキャッシュ更新
    time.sleep(0.5)

    pattern = f"{base_date}_*_material.md"
    material_files = sorted(material_dir.glob(pattern)) if material_dir.exists() else []

    steps: list[Step] = []
    for material_file in material_files:
        material_name = material_file.stem
        prompt = (
            f"「週次パイプラインモード」で実行してください。"
            f" 素材シート: {material_file}"
            f" 基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )
        steps.append(Step(
            name=f"poc-planner-{material_name}",
            executor=AgentExecutor(
                agent_name="tech-poc-planner",
                prompt_text=prompt,
            ),
            timeout=900,
            params=StepParams(
                slack=SlackParams(enabled=False),
            ),
        ))

    return steps


def main() -> None:
    config = PipelineConfig(
        name="poc-planner",
        build_steps=build_steps,
        default_base_date=_default_base_date,
    )
    run_pipeline(config)



if __name__ == "__main__":
    main()
