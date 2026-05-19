#!/usr/bin/env python3.12
"""
invoke-agent: 手動実行用CLIラッパー

目的:
    コマンドライン引数から Step を1つ構築し、run_pipeline() と同じ
    実行ロジック（StepParams → YAMLブロック生成 → AI CLI実行）で処理する。
    パイプラインと手動実行で実行パスが統一される。

使い方:
    python3.12 scripts/invoke-agent.py --agent web-searcher --prompt "Deno 2のNode互換性について調べて"
    python3.12 scripts/invoke-agent.py --agent tech-trend-scout --base-date 2026-05-16
    python3.12 scripts/invoke-agent.py --agent web-searcher --prompt "..." --output-path "Documents/works/research_materials/2026-05-17_deno.md"
    python3.12 scripts/invoke-agent.py --agent web-searcher --prompt "..." --no-slack
    python3.12 scripts/invoke-agent.py --agent web-searcher --prompt "..." --slack-channel C12345 --slack-thread-ts 1234567890.123456

出力: エージェント実行結果 + オプショナルなSlack通知
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替)
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import os
from datetime import datetime, timedelta, timezone

from _pipeline_common import (
    HOME,
    JST,
    AgentExecutor,
    ExecutionContext,
    OutputParams,
    PipelineLogger,
    SlackParams,
    Step,
    StepParams,
    execute_steps,
    load_env,
    now_jst,
    start_caffeinate,
    stop_caffeinate,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="エージェント手動実行ラッパー（統一ステップモデル）",
    )
    parser.add_argument(
        "--agent", required=True,
        help="エージェント名（.kiro/agents/ のエージェント名）",
    )
    parser.add_argument(
        "--prompt", default="",
        help="エージェントに渡すプロンプトテキスト",
    )
    parser.add_argument(
        "--base-date", default="",
        help="基準日（省略時: 昨日）",
    )
    parser.add_argument(
        "--output-path", default="",
        help="出力先ファイルパス（省略時: エージェントのデフォルト）",
    )
    parser.add_argument(
        "--input-path", default="",
        help="入力ファイルパス（source_type: file）",
    )
    parser.add_argument(
        "--input-theme", default="",
        help="入力テーマ（source_type: theme）",
    )
    parser.add_argument(
        "--input-url", default="",
        help="入力URL（source_type: url）",
    )
    parser.add_argument(
        "--format-ref", default="",
        help="出力フォーマット参照パス",
    )
    parser.add_argument(
        "--no-slack", action="store_true",
        help="Slack通知を無効化",
    )
    parser.add_argument(
        "--slack-channel", default="",
        help="Slack通知先チャンネルID",
    )
    parser.add_argument(
        "--slack-thread-ts", default="",
        help="Slack通知先スレッドTS",
    )
    parser.add_argument(
        "--timeout", type=int, default=900,
        help="タイムアウト秒（デフォルト: 900）",
    )
    args = parser.parse_args()

    # 基準日
    if args.base_date:
        base_date = args.base_date
    else:
        yesterday = datetime.now(tz=JST) - timedelta(days=1)
        base_date = yesterday.strftime("%Y-%m-%d")

    # プロンプト構築
    prompt = args.prompt or (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )

    # InputParams
    from _pipeline_common import InputParams
    input_params = None
    if args.input_path:
        input_params = InputParams(source_type="file", source_path=args.input_path)
    elif args.input_theme:
        input_params = InputParams(source_type="theme", source_theme=args.input_theme)
    elif args.input_url:
        input_params = InputParams(source_type="url", source_url=args.input_url)

    # OutputParams
    output_params = None
    if args.output_path:
        output_params = OutputParams(path=args.output_path, format_ref=args.format_ref)

    # SlackParams
    slack_params = SlackParams(
        enabled=not args.no_slack,
        channel=args.slack_channel,
        thread_ts=args.slack_thread_ts,
        thread_mode="compact",
    )

    # Step 構築
    step = Step(
        name=args.agent,
        executor=AgentExecutor(agent_name=args.agent, prompt_text=prompt),
        timeout=args.timeout,
        params=StepParams(
            input=input_params,
            output=output_params,
            slack=slack_params,
        ),
    )

    # 環境準備
    load_env()
    caffeinate_pid = start_caffeinate()

    # MCP用環境変数設定（kiro-cliは${VAR}形式の展開を未サポートのため直接設定）
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("SLACK_REFERENCE_BOT_TOKEN", "")
    os.environ["SLACK_TEAM_ID"] = os.environ.get("SLACK_REFERENCE_TEAM_ID", "")

    # ログ
    log_dir = HOME / "logs" / "jobs" / "invoke-agent"
    log_dir.mkdir(parents=True, exist_ok=True)
    plogger = PipelineLogger(
        "invoke-agent", log_dir=log_dir,
        max_lines=500, keep_lines=100,
        agent_max_lines=500, agent_keep_lines=100,
    )

    plogger.info(f"invoke-agent: {args.agent}（基準日: {base_date}）")

    # 実行
    exec_context = ExecutionContext(
        job_file=None,
        use_job_file=False,
        base_date=base_date,
        plogger=plogger,
        slack_channel=args.slack_channel,
        slack_thread_ts=args.slack_thread_ts,
    )
    success, failed, skipped = execute_steps([step], exec_context)

    stop_caffeinate(caffeinate_pid)

    if failed > 0:
        sys.exit(1)



if __name__ == "__main__":
    main()
