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
import time
from datetime import datetime
from pathlib import Path

from _pipeline_common import (
    HOME,
    JST,
    MAX_AGENT_LOG_LINES,
    SCRIPTS_DIR,
    PipelineConfig,
    log_error,
    now_jst,
    rotate_log,
    run_ai_command,
    run_pipeline,
)

# ─── Weekly固有の定数 ────────────────────────────────────────────

LOG_DIR = HOME / "logs" / "jobs" / "scout_weekly"

AGENTS = [
    "tech-event-scout",
    "github-public-digest-scout",
    "github-org-digest-scout",
    "tech-blog-material-scout",
    "github-verification-candidate-scout",
    "tech-poc-planner",
    "gws-digest-scout",
    "slack-digest-scout",
    "notion-digest-scout",
]

# 週次パイプラインモード対象エージェント
WEEKLY_PIPELINE_MODE_AGENTS = {
    "tech-event-scout",
    "tech-blog-material-scout",
    "github-verification-candidate-scout",
    "tech-poc-planner",
}

NOTIFY_FILE_MAP: dict[str, str] = {
    "slack-digest-scout": "scout_reports/slack_trends/weekly/{date}_slack_weekly_digest.md",
    "gws-digest-scout": "scout_reports/gws_trends/weekly/{date}_gws_weekly_digest.md",
    "notion-digest-scout": "scout_reports/notion_trends/weekly/{date}_notion_weekly_digest.md",
    "github-org-digest-scout": "scout_reports/github_org_trends/weekly/{date}_github-org_weekly_digest.md",
    "github-public-digest-scout": "scout_reports/github_public_trends/weekly/{date}_github-public_weekly_digest.md",
    "tech-event-scout": "scout_reports/tech_events/weekly/{date}_tech_events.md",
}


# ─── Weekly固有のコールバック関数 ────────────────────────────────

def _default_base_date() -> str:
    """weeklyのデフォルト基準日: 当日。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d")


def _rss_fetch_hook(base_date: str, scripts_dir: Path) -> None:
    """RSSフィード事前取得（weekly用: --no-filter付き）。"""
    rss_script = scripts_dir / "fetch-rss-feeds.py"
    if not rss_script.exists():
        print("   ⚠️  RSSスクリプト未検出（スキップ）")
        return

    for category in ["tech_events", "lifestyle_events"]:
        result = subprocess.run(
            ["python3.12", str(rss_script), "--category", category,
             "--date", base_date, "--no-filter"],
            capture_output=True, text=True,
        )
        status = "✅" if result.returncode == 0 else "⚠️ "
        print(f"   {status} {category}")


def _build_prompt(agent: str, base_date: str) -> str:
    """weeklyのプロンプト構築。WEEKLY_PIPELINE_MODE_AGENTS は週次モード付き。"""
    if agent in WEEKLY_PIPELINE_MODE_AGENTS:
        return (
            f"「週次パイプラインモード」で実行してください。"
            f"基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )
    else:
        return (
            f"基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )


def _pre_agent_hook(agent: str, base_date: str) -> str | None:
    """tech-poc-planner は Step 2.5 で個別実行するためスキップ。"""
    if agent == "tech-poc-planner":
        return "Step 2.5で個別実行（スキップ）"
    return None


def _post_agents_hook(base_date: str) -> None:
    """全エージェント実行後: tech-poc-planner 個別実行。"""
    run_poc_planner(base_date)


def _post_notify_hook(base_date: str) -> None:
    """通知後: 参照データ鮮度チェック・更新。"""
    run_freshness_check(base_date)


# ─── Weekly固有関数 ──────────────────────────────────────────────

def run_poc_planner(base_date: str) -> None:
    """tech-poc-planner を素材シート1件ごとに個別実行する。"""
    planner_now = now_jst()
    print(f"[{planner_now}] Step 2.5: tech-poc-planner 個別実行...")

    material_dir = (HOME / "Documents" / "works" /
                    "scout_reports" / "tech_blog_materials" / "weekly")
    planner_log = LOG_DIR / "tech-poc-planner.log"
    rotate_log(planner_log, MAX_AGENT_LOG_LINES, keep_lines=100)

    # ファイルシステムキャッシュ更新
    time.sleep(1)

    # 当該基準日の素材シートを列挙
    pattern = f"{base_date}_*_material.md"
    material_files = sorted(material_dir.glob(pattern)) if material_dir.exists() else []

    if not material_files:
        print(f"[{planner_now}]    ⚠️  素材シートなし（{pattern}）")
        return

    print(f"[{planner_now}]    📄 素材シート {len(material_files)} 件検出")

    planner_success = 0
    planner_failed = 0

    for material_file in material_files:
        material_name = material_file.name
        plan_start = now_jst()
        print(f"[{plan_start}]    🔄 tech-poc-planner: {material_name}")

        prompt = (
            f"「週次パイプラインモード」で実行してください。"
            f" 素材シート: {material_file}"
            f" 基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )

        if run_ai_command(prompt, planner_log, agent_name="tech-poc-planner"):
            print(f"[{now_jst()}]       ✅ {material_name} 完了")
            planner_success += 1
        else:
            print(f"[{now_jst()}]       ❌ {material_name} 失敗")
            print(f"[{now_jst()}]       💡 再実行: python3.12 scripts/run-weekly-pipeline.py {base_date}")
            log_error("weekly-pipeline", f"tech-poc-planner:{material_name}", "AI command exit non-zero")
            planner_failed += 1

    planner_end = now_jst()
    print(f"[{planner_end}]    📊 tech-poc-planner: ✅{planner_success}件 / ❌{planner_failed}件")


def run_freshness_check(base_date: str) -> None:
    """参照データの鮮度チェックと更新を行う。"""
    refresh_now = now_jst()
    print(f"[{refresh_now}] Step 5: 参照データ鮮度チェック...")

    freshness_script = SCRIPTS_DIR / "check-directory-freshness.py"
    refresh_log = LOG_DIR / "reference-refresh.log"
    rotate_log(refresh_log, MAX_AGENT_LOG_LINES, keep_lines=100)

    # Slack鮮度チェック
    slack_stale = check_freshness(freshness_script, "slack", 7)
    notion_stale = check_freshness(freshness_script, "notion", 14)

    # Slack更新
    if slack_stale:
        print(f"[{now_jst()}]    🔄 Slack ユーザーディレクトリ更新中...")
        prompt = "ワークフローに従って実行してください。"
        if run_ai_command(prompt, refresh_log, agent_name="slack-user-directory-updater"):
            print(f"[{now_jst()}]    ✅ Slack ユーザーディレクトリ更新完了")
        else:
            print(f"[{now_jst()}]    ⚠️  Slack ユーザーディレクトリ更新失敗（続行）")
            log_error("weekly-pipeline", "reference-refresh:slack", "更新失敗")
    else:
        print(f"[{refresh_now}]    ✅ Slack データ鮮度OK（スキップ）")

    # Notion更新
    if notion_stale:
        print(f"[{now_jst()}]    🔄 Notion ユーザーディレクトリ更新中...")
        prompt = "ワークフローに従って実行してください。"
        if run_ai_command(prompt, refresh_log, agent_name="notion-user-directory-updater"):
            print(f"[{now_jst()}]    ✅ Notion ユーザーディレクトリ更新完了")
        else:
            print(f"[{now_jst()}]    ⚠️  Notion ユーザーディレクトリ更新失敗（続行）")
            log_error("weekly-pipeline", "reference-refresh:notion", "更新失敗")
    else:
        print(f"[{refresh_now}]    ✅ Notion データ鮮度OK（スキップ）")


def check_freshness(script: Path, dir_type: str, max_age_days: int) -> bool:
    """鮮度チェックスクリプトを実行し、stale かどうかを返す。"""
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


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    config = PipelineConfig(
        name="weekly",
        log_dir=LOG_DIR,
        agents=AGENTS,
        notify_file_map=NOTIFY_FILE_MAP,
        create_jobs_script="create-weekly-jobs.py",
        default_base_date=_default_base_date,
        rss_fetch_hook=_rss_fetch_hook,
        build_prompt=_build_prompt,
        resolve_notify_path=None,
        pre_agent_hook=_pre_agent_hook,
        post_agents_hook=_post_agents_hook,
        post_notify_hook=_post_notify_hook,
    )
    run_pipeline(config)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
