#!/usr/bin/env python3.12
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

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from _pipeline_common import (
    HOME,
    JST,
    PipelineConfig,
    now_jst,
    run_pipeline,
)

# ─── Daily固有の定数 ─────────────────────────────────────────────

LOG_DIR = HOME / "logs" / "jobs" / "scout_daily"

AGENTS = [
    "tech-trend-scout",
    "biz-car-trend-scout",
    "run-academic-trend-scout-pipeline.py",
    "lifestyle-event-scout",
    "rss-source-updater",
    "github-public-trend-scout",
    "github-org-trend-scout",
    "run-gws-trend-scout-pipeline.py",
    "slack-trend-scout",
    "notion-trend-scout",
]

NOTIFY_FILE_MAP: dict[str, str] = {
    "tech-trend-scout": "scout_histories/tech_trends/daily/{date}_tech_trends.md",
    "biz-car-trend-scout": "scout_histories/biz_car_trends/daily/{date}_biz_car_trends.md",
    "academic-trend-scout-pipeline": "scout_histories/academic_trends/daily/{date}_academic_trends.md",
    "gws-trend-scout-pipeline": "scout_histories/gws_trends/daily/{date}_gws_daily.md",
    "slack-trend-scout": "scout_histories/slack_trends/daily/{date}_slack_daily.md",
    "github-org-trend-scout": "scout_histories/github_org_trends/daily/{date}_github-org_daily.md",
    "github-public-trend-scout": "scout_histories/github_public_trends/daily/{date}_github-public_daily.md",
    "notion-trend-scout": "scout_histories/notion_trends/daily/{date}_notion_daily.md",
}

# lifestyle-event-scoutは曜日によって出力ファイル名が変わるため動的に解決
LIFESTYLE_THEME_MAP: dict[int, str] = {
    0: "outing",       # 月曜日
    1: "experience",   # 火曜日
    2: "culture",      # 水曜日
    3: "learning",     # 木曜日
    4: "food-living",  # 金曜日
    5: "money-life",   # 土曜日
    # 6: 日曜日 = 週次サマリー（weekly/に出力）
}


# ─── Daily固有のコールバック関数 ─────────────────────────────────

def _default_base_date() -> str:
    """dailyのデフォルト基準日: 昨日。"""
    yesterday = datetime.now(tz=JST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _sync_claude_agents(base_date: str, scripts_dir: Path) -> None:
    """kiro→claudeエージェント定義を同期する(非致命的)。"""
    sync_script = scripts_dir / "sync-claude-agents.py"
    if not sync_script.exists():
        print(f"[{now_jst()}] ⚠️  sync-claude-agents.py 未検出（スキップ）")
        return

    print(f"[{now_jst()}] 🔄 claude agent定義の同期...")
    result = subprocess.run(
        ["python3.12", str(sync_script)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in (result.stderr or "").strip().splitlines():
            print(f"   {line}")
    else:
        print(f"[{now_jst()}]    ⚠️  同期失敗(続行): "
              f"{(result.stderr or result.stdout).strip()[:200]}")


def _rss_fetch_hook(base_date: str, scripts_dir: Path) -> None:
    """RSSフィード事前取得（daily用）。"""
    rss_script = scripts_dir / "fetch-rss-feeds.py"
    if not rss_script.exists():
        print("   ⚠️  RSSスクリプト未検出（スキップ）")
        return

    today_date = datetime.now(tz=JST).strftime("%Y-%m-%d")
    for category in ["tech", "biz_car", "academic", "lifestyle_events"]:
        # lifestyle_eventsは当日基準（エージェントが当日の曜日テーマで動作するため）
        feed_date = today_date if category == "lifestyle_events" else base_date
        result = subprocess.run(
            ["python3.12", str(rss_script), "--category", category, "--date", feed_date],
            capture_output=True, text=True,
        )
        status = "✅" if result.returncode == 0 else "⚠️ "
        print(f"   {status} {category} (date={feed_date})")


def _build_prompt(agent: str, base_date: str) -> str:
    """dailyのプロンプト構築。lifestyle-event-scoutは当日基準。"""
    if agent == "lifestyle-event-scout":
        agent_base_date = datetime.now(tz=JST).strftime("%Y-%m-%d")
    else:
        agent_base_date = base_date

    return (
        f"基準日は {agent_base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )


def _resolve_notify_path(agent: str, base_date: str) -> Path | None:
    """daily通知ファイルパス解決。lifestyle-event-scoutは曜日テーマで動的解決。"""
    if agent != "lifestyle-event-scout":
        return None  # テンプレートマップに委譲

    today_date = datetime.now(tz=JST).strftime("%Y-%m-%d")
    target_date = datetime.now(tz=JST)
    weekday = target_date.weekday()
    theme = LIFESTYLE_THEME_MAP.get(weekday)

    if theme is None:
        # 日曜日: 週次サマリー
        return (HOME / "Documents" / "works" /
                f"scout_histories/lifestyle_events/weekly/{today_date}_lifestyle_weekly_summary.md")
    else:
        return (HOME / "Documents" / "works" /
                f"scout_histories/lifestyle_events/daily/{today_date}_lifestyle_{theme}.md")


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    config = PipelineConfig(
        name="daily",
        log_dir=LOG_DIR,
        agents=AGENTS,
        notify_file_map=NOTIFY_FILE_MAP,
        create_jobs_script="create-daily-jobs.py",
        default_base_date=_default_base_date,
        pre_pipeline_hook=_sync_claude_agents,
        rss_fetch_hook=_rss_fetch_hook,
        build_prompt=_build_prompt,
        resolve_notify_path=_resolve_notify_path,
        pre_agent_hook=None,
        post_agents_hook=None,
        post_notify_hook=None,
    )
    run_pipeline(config)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
