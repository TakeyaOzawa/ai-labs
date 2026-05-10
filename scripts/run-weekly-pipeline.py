#!/usr/bin/env python3.12
"""
run-weekly-pipeline: 週次scoutパイプラインをkiro-cliで実行する（タスク管理付き）

目的:
    週次scoutパイプラインの全エージェントを順次実行し、
    digest集約→イベント収集→ブログ素材→ブログ企画を一括で行う。
    ジョブファイルベース進捗管理を行う。

使い方:
    python3.12 scripts/run-weekly-pipeline.py [基準日]
    python3.12 scripts/run-weekly-pipeline.py 2026-05-07
    python3.12 scripts/run-weekly-pipeline.py --no-job-file

出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
依存: kiro-cli, python3.12 (fetch-rss-feeds.py)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
LOG_DIR = HOME / "logs" / "jobs" / "scout_weekly"
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"

AGENTS = [
    "slack-digest-scout",
    "gws-digest-scout",
    "notion-digest-scout",
    "github-org-digest-scout",
    "github-public-digest-scout",
    "tech-event-scout",
    "tech-blog-material-scout",
    "tech-poc-planner",
]

# 週次パイプラインモード対象エージェント
WEEKLY_PIPELINE_MODE_AGENTS = {
    "tech-event-scout",
    "tech-blog-material-scout",
    "tech-poc-planner",
}

NOTIFY_FILE_MAP: dict[str, str] = {
    "slack-digest-scout": "scout_histories/slack_trends/weekly/{date}_slack_weekly_digest.md",
    "gws-digest-scout": "scout_histories/gws_trends/weekly/{date}_gws_weekly_digest.md",
    "notion-digest-scout": "scout_histories/notion_trends/weekly/{date}_notion_weekly_digest.md",
    "github-org-digest-scout": "scout_histories/github_org_trends/weekly/{date}_github-org_weekly_digest.md",
    "github-public-digest-scout": "scout_histories/github_public_trends/weekly/{date}_github-public_weekly_digest.md",
    "tech-event-scout": "scout_histories/tech_events/weekly/{date}_tech_events.md",
}

MAX_LOG_LINES = 1000
MAX_AGENT_LOG_LINES = 500


# ─── ユーティリティ ──────────────────────────────────────────────

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def rotate_log(log_file: Path, max_lines: int, keep_lines: int = 200) -> None:
    """ログファイルが max_lines を超えていたら末尾 keep_lines 行に切り詰める。"""
    if not log_file.exists():
        return
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > max_lines:
        log_file.write_text("\n".join(lines[-keep_lines:]) + "\n", encoding="utf-8")


def load_env() -> None:
    """環境変数をロードする（launchd環境対応）。"""
    if os.environ.get("MY_SLACK_OAUTH_TOKEN"):
        return

    result = subprocess.run(
        [str(PLATFORM_CMD), "source-env"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ[key] = value


def run_kiro_cli(prompt: str, log_file: Path) -> bool:
    """kiro-cliを実行し、成功/失敗を返す。"""
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(
            ["kiro-cli", "chat", "--trust-all-tools", "--no-interactive", prompt],
            stdout=f, stderr=subprocess.STDOUT,
        )
    return result.returncode == 0


def log_error(pipeline: str, agent: str, message: str) -> None:
    """error.logに親タスク > 子タスクの2階層ヘッダー付きでエラーを記録する。"""
    timestamp = now_jst()
    print(f"[{timestamp}] [{pipeline}] > [{agent}] {message}", file=sys.stderr)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    # オプション解析
    use_job_file = True
    positional_args: list[str] = []

    for arg in sys.argv[1:]:
        if arg == "--no-job-file":
            use_job_file = False
        else:
            positional_args.append(arg)

    # 基準日
    if positional_args:
        base_date = positional_args[0]
    else:
        base_date = datetime.now(tz=JST).strftime("%Y-%m-%d")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # スリープ防止
    caffeinate_pid = start_caffeinate()

    # 環境変数ロード
    load_env()

    # 収集フェーズ用の環境変数設定
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("SLACK_REFERENCE_BOT_TOKEN", "")
    os.environ["SLACK_TEAM_ID"] = os.environ.get("SLACK_REFERENCE_TEAM_ID", "")

    # ログローテーション
    log_file = LOG_DIR / "pipeline.log"
    rotate_log(log_file, MAX_LOG_LINES)

    # error.log ローテーション（launchd StandardErrorPath）
    error_log = LOG_DIR / "pipeline-error.log"
    rotate_log(error_log, MAX_LOG_LINES)

    print(f"[{now_jst()}] 📋 週次scoutパイプライン起動（基準日: {base_date}）")

    # ─── Step 0: ジョブファイル生成 ───────────────────────────────
    job_file: Path | None = None
    if use_job_file:
        print(f"[{now_jst()}] Step 0: ジョブファイル生成...")
        job_file = create_job_file(base_date)
        if job_file:
            print(f"[{now_jst()}]    ジョブファイル: {job_file}")
            update_job(job_file, scope="parent",
                        updates={"status": "running", "started_at": now_jst()})
        else:
            print(f"[{now_jst()}] ⚠️  ジョブファイル生成失敗。進捗管理なしで続行。")
            use_job_file = False

    # ─── Step 1: RSSフィード事前取得（イベント系） ────────────────
    print(f"[{now_jst()}] Step 1: RSSフィード事前取得...")
    rss_script = SCRIPTS_DIR / "fetch-rss-feeds.py"
    if rss_script.exists():
        for category in ["tech_events", "lifestyle_events"]:
            result = subprocess.run(
                ["python3.12", str(rss_script), "--category", category,
                 "--date", base_date, "--no-filter"],
                capture_output=True, text=True,
            )
            status = "✅" if result.returncode == 0 else "⚠️ "
            print(f"   {status} {category}")
    else:
        print("   ⚠️  RSSスクリプト未検出（スキップ）")

    # ─── Step 2: 週次エージェントを順次実行 ──────────────────────
    print(f"[{now_jst()}] Step 2: 週次scoutエージェント実行開始...")

    success = 0
    failed = 0
    failed_names: list[str] = []

    for agent in AGENTS:
        agent_start = now_jst()
        print(f"[{agent_start}] 🔄 {agent} 実行中...")

        agent_log = LOG_DIR / f"{agent}.log"
        rotate_log(agent_log, MAX_AGENT_LOG_LINES, keep_lines=100)

        # ジョブファイル: running に更新
        child_job_id = ""
        if use_job_file and job_file:
            child_job_id = get_child_job_id(job_file, agent)
            if child_job_id:
                update_job(job_file, job_id=child_job_id,
                            updates={"status": "running", "started_at": agent_start})
                update_job(job_file, scope="parent",
                            updates={"status_detail": f"{agent} 実行中"})

        # tech-poc-planner は Step 2.5 で個別実行
        if agent == "tech-poc-planner":
            print(f"[{agent_start}]    ⏭️  {agent}: Step 2.5で個別実行（スキップ）")
            success += 1
            if use_job_file and child_job_id:
                update_job(job_file, job_id=child_job_id, updates={
                    "status": "completed", "completed_at": agent_start,
                    "status_detail": "Step 2.5で個別実行",
                })
            continue

        # プロンプト構築
        if agent in WEEKLY_PIPELINE_MODE_AGENTS:
            prompt = (
                f"{agent} エージェントとして「週次パイプラインモード」で動作してください。"
                f" ~/.shared-ai/prompts/{agent}.md をreadFileで読み込み、"
                f"そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
                f"基準日は {base_date} です。"
                f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
            )
        else:
            prompt = (
                f"{agent} エージェントとして動作してください。"
                f" ~/.shared-ai/prompts/{agent}.md をreadFileで読み込み、"
                f"そこに記載されたワークフローに従って実行してください。"
                f"基準日は {base_date} です。"
                f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
            )

        if run_kiro_cli(prompt, agent_log):
            agent_end = now_jst()
            print(f"[{agent_end}]    ✅ {agent} 完了")
            success += 1
            if use_job_file and child_job_id:
                update_job(job_file, job_id=child_job_id,
                            updates={"status": "completed", "completed_at": agent_end})
        else:
            agent_end = now_jst()
            print(f"[{agent_end}]    ❌ {agent} 失敗（ログ: {agent_log}）")
            print(f"[{agent_end}]    💡 再実行: kiro-cli chat --trust-all-tools --no-interactive \"{prompt}\"")
            log_error("weekly-pipeline", agent, "kiro-cli exit non-zero")
            failed += 1
            failed_names.append(agent)
            if use_job_file and child_job_id:
                update_job(job_file, job_id=child_job_id, updates={
                    "status": "failed", "error": "kiro-cli exit non-zero",
                    "completed_at": agent_end,
                })

    # ─── Step 2.5: tech-poc-planner 個別実行 ─────────────────────
    run_poc_planner(base_date)

    # ─── Step 3: 親タスク完了処理 ────────────────────────────────
    end_now = now_jst()
    total = success + failed

    if use_job_file and job_file:
        if failed > 0:
            update_job(job_file, scope="parent", updates={
                "status": "failed", "completed_at": end_now,
                "status_detail": f"{failed}件失敗: {' '.join(failed_names)}",
                "error": f"{failed}/{total} jobs failed",
            })
        else:
            update_job(job_file, scope="parent", updates={
                "status": "completed", "completed_at": end_now,
                "status_detail": "全子タスク完了",
            })

    # ─── Step 4: Slack通知 ───────────────────────────────────────
    notify_now = now_jst()
    print(f"[{notify_now}] Step 4: Slack通知...")

    # 通知用に環境変数を切り替え
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("MY_SLACK_OAUTH_TOKEN", "")

    notify_success = 0
    notify_skipped = 0
    notify_log = LOG_DIR / "slack-notify.log"
    rotate_log(notify_log, MAX_AGENT_LOG_LINES, keep_lines=100)

    for agent in AGENTS:
        template = NOTIFY_FILE_MAP.get(agent, "")
        if not template:
            notify_skipped += 1
            continue

        file_path = HOME / "Documents" / "works" / template.format(date=base_date)
        if not file_path.exists():
            print(f"   ⏭️  {agent}: 出力ファイルなし（スキップ）")
            notify_skipped += 1
            continue

        print(f"[{now_jst()}]    📨 {agent} 通知中...")
        notify_prompt = (
            f"slack-notifier エージェントとして動作してください。"
            f" ~/.shared-ai/prompts/slack-notifier.md をreadFileで読み込み、"
            f"そこに記載されたワークフローに従って実行してください。"
            f" file_path={file_path}"
        )

        if run_kiro_cli(notify_prompt, notify_log):
            print(f"[{now_jst()}]    ✅ {agent} 通知完了")
            notify_success += 1
        else:
            print(f"[{now_jst()}]    ⚠️  {agent} 通知失敗（レポート作成は成功扱い）")
            log_error("weekly-pipeline", f"slack-notify:{agent}", "通知失敗")

    notify_end = now_jst()
    print(f"[{notify_end}] 📨 通知完了: ✅{notify_success}件 / ⏭️{notify_skipped}件スキップ")

    # ─── Step 5: 参照データ鮮度チェック・更新 ────────────────────
    run_freshness_check(base_date)

    # ─── Step 6: 完了サマリー ────────────────────────────────────
    final_now = now_jst()
    print(f"[{final_now}] 📊 実行完了: ✅{success}件 / ❌{failed}件 (全{total}件)")
    if failed > 0:
        print(f"[{final_now}]    失敗: {' '.join(failed_names)}")
    if use_job_file and job_file:
        print(f"[{final_now}]    ジョブファイル: {job_file}")
    print(f"[{final_now}] ✅ 週次scoutパイプライン完了（基準日: {base_date}）")

    # スリープ防止解除
    stop_caffeinate(caffeinate_pid)


# ─── Step 2.5: tech-poc-planner ──────────────────────────────────

def run_poc_planner(base_date: str) -> None:
    """tech-poc-planner を素材シート1件ごとに個別実行する。"""
    planner_now = now_jst()
    print(f"[{planner_now}] Step 2.5: tech-poc-planner 個別実行...")

    material_dir = (HOME / "Documents" / "works" /
                    "scout_histories" / "tech_blog_materials" / "weekly")
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
            f"tech-poc-planner エージェントとして「週次パイプラインモード」で動作してください。"
            f" ~/.shared-ai/prompts/tech-poc-planner.md をreadFileで読み込み、"
            f"そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
            f" 素材シート: {material_file}"
            f" 基準日は {base_date} です。"
            f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        )

        if run_kiro_cli(prompt, planner_log):
            print(f"[{now_jst()}]       ✅ {material_name} 完了")
            planner_success += 1
        else:
            print(f"[{now_jst()}]       ❌ {material_name} 失敗")
            print(f"[{now_jst()}]       💡 再実行: kiro-cli chat --trust-all-tools --no-interactive \"{prompt}\"")
            log_error("weekly-pipeline", f"tech-poc-planner:{material_name}", "kiro-cli exit non-zero")
            planner_failed += 1

    planner_end = now_jst()
    print(f"[{planner_end}]    📊 tech-poc-planner: ✅{planner_success}件 / ❌{planner_failed}件")


# ─── Step 5: 鮮度チェック ────────────────────────────────────────

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
        prompt = (
            "slack-user-directory-updater エージェントとして動作してください。"
            " ~/.shared-ai/prompts/slack-user-directory-updater.md をreadFileで読み込み、"
            "そこに記載されたワークフローに従って実行してください。"
        )
        if run_kiro_cli(prompt, refresh_log):
            print(f"[{now_jst()}]    ✅ Slack ユーザーディレクトリ更新完了")
        else:
            print(f"[{now_jst()}]    ⚠️  Slack ユーザーディレクトリ更新失敗（続行）")
            log_error("weekly-pipeline", "reference-refresh:slack", "更新失敗")
    else:
        print(f"[{refresh_now}]    ✅ Slack データ鮮度OK（スキップ）")

    # Notion更新
    if notion_stale:
        print(f"[{now_jst()}]    🔄 Notion ユーザーディレクトリ更新中...")
        prompt = (
            "notion-user-directory-updater エージェントとして動作してください。"
            " ~/.shared-ai/prompts/notion-user-directory-updater.md をreadFileで読み込み、"
            "そこに記載されたワークフローに従って実行してください。"
        )
        if run_kiro_cli(prompt, refresh_log):
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


# ─── ヘルパー関数 ────────────────────────────────────────────────

def start_caffeinate() -> str:
    """スリープ防止を開始し、プロセスIDを返す。"""
    pid = str(os.getpid())
    result = subprocess.run(
        [str(PLATFORM_CMD), "caffeinate-start", pid],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def stop_caffeinate(cafe_pid: str) -> None:
    """スリープ防止を停止する。"""
    if cafe_pid and cafe_pid != "0":
        subprocess.run(
            [str(PLATFORM_CMD), "caffeinate-stop", cafe_pid],
            capture_output=True, text=True,
        )


def create_job_file(base_date: str) -> Path | None:
    """ジョブファイルを生成し、パスを返す。"""
    result = subprocess.run(
        ["python3.12", str(SCRIPTS_DIR / "create-weekly-jobs.py"), base_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if "ファイル:" in line:
            path_str = line.split("ファイル:")[1].strip()
            path = Path(path_str)
            if path.exists():
                return path
    return None


def get_child_job_id(job_file: Path, job_name: str) -> str:
    """ジョブファイルから指定ジョブ名のIDを取得する。"""
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)
    for child in data.get("child_jobs", []):
        if child.get("job_name") == job_name:
            return child.get("job_id", "")
    return ""


def update_job(job_file: Path, job_id: str = "", scope: str = "child",
                updates: dict | None = None) -> None:
    """ジョブを更新する。"""
    if updates is None:
        return

    cmd = [
        "python3.12", str(SCRIPTS_DIR / "update-job.py"),
        "--job-file", str(job_file),
        "--scope", scope if scope == "parent" else "child",
        "--set", json.dumps(updates, ensure_ascii=False),
    ]
    if scope != "parent" and job_id:
        cmd.extend(["--job-id", job_id])

    subprocess.run(cmd, capture_output=True, text=True)



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
