#!/usr/bin/env python3.12
"""
run-academic-trend-scout-pipeline: アカデミックトレンドスカウトのパイプライン化実行

目的:
    academic-trend-scoutの単一コンテキスト実行を廃止し、分野ごとに独立した
    AIコマンドプロセスで実行する。月曜日のarXivフィード1400件超でも
    コンテキスト圧迫なく処理できるようにする。

使い方:
    python3.12 scripts/run-academic-trend-scout-pipeline.py [基準日]
    python3.12 scripts/run-academic-trend-scout-pipeline.py 2026-05-11

出力: Documents/works/scout_reports/academic_trends/daily/{date}_academic_trends.md
依存: python3.12, kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替), split-academic-feeds.py, merge-academic-intermediate-files.py
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _pipeline_common import run_ai_command, _notify_slack_reply, run_slack_notify

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
FEED_DIR = HOME / "Documents" / "works" / "scout_reports" / "academic_trends" / "daily"
TMP_DIR = FEED_DIR / "tmp"
OUTPUT_DIR = FEED_DIR


# ─── 分野定義 ────────────────────────────────────────────────────

@dataclass
class FieldConfig:
    """分野ごとのパラメータ定義。"""

    name: str           # ml_ai / cv_robotics / se_it / economics / behavioral_biz / interdisciplinary
    display_name: str   # 表示名
    has_feed: bool      # フィードファイルがあるか


FIELD_CONFIGS = [
    FieldConfig("ml_ai", "機械学習・AI", True),
    FieldConfig("cv_robotics", "コンピュータビジョン・ロボティクス", True),
    FieldConfig("se_it", "IT・情報科学", True),
    FieldConfig("economics", "経済学", True),
    FieldConfig("behavioral_biz", "行動心理学・経済心理学・ビジネス", False),
    FieldConfig("interdisciplinary", "学際・応用・IoT", False),
]


# ─── ユーティリティ ──────────────────────────────────────────────

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


# ─── ジョブ管理連携 ──────────────────────────────────────────────

@dataclass
class JobContext:
    """親パイプラインから渡されたジョブ管理コンテキスト。"""

    job_file: Path | None
    parent_job_id: str

    @property
    def enabled(self) -> bool:
        return self.job_file is not None and self.parent_job_id != ""


def load_job_context() -> JobContext:
    """環境変数からジョブコンテキストを読み込む。"""
    job_file_str = os.environ.get("PIPELINE_JOB_FILE", "")
    parent_job_id = os.environ.get("PIPELINE_PARENT_JOB_ID", "")
    job_file = Path(job_file_str) if job_file_str and Path(job_file_str).exists() else None
    return JobContext(job_file=job_file, parent_job_id=parent_job_id)


def update_grandchild_job(ctx: JobContext, job_name: str, updates: dict) -> None:
    """grandchildジョブのステータスを更新する。"""
    if not ctx.enabled:
        return
    try:
        with open(ctx.job_file, encoding="utf-8") as f:
            data = json.load(f)
        job_id = _find_job_id(data.get("child_jobs", []), job_name)
        if not job_id:
            return
        cmd = [
            "python3.12", str(SCRIPTS_DIR / "update-job.py"),
            "--job-file", str(ctx.job_file),
            "--job-id", job_id,
            "--set", json.dumps(updates, ensure_ascii=False),
        ]
        subprocess.run(cmd, capture_output=True, text=True)
    except (OSError, json.JSONDecodeError):
        pass


def _find_job_id(jobs: list[dict], job_name: str) -> str:
    """ジョブツリーを再帰的に探索し、指定名のジョブIDを返す。"""
    for job in jobs:
        if job.get("job_name") == job_name:
            return job.get("job_id", "")
        found = _find_job_id(job.get("child_jobs", []), job_name)
        if found:
            return found
    return ""


# ─── Step 0: 対象日決定 + ディレクトリ準備 ───────────────────────

def step0_prepare(base_date_str: str | None) -> str:
    """対象日を決定し、ディレクトリを準備する。"""
    if base_date_str:
        base_date = base_date_str
    else:
        yesterday = datetime.now(tz=JST) - timedelta(days=1)
        base_date = yesterday.strftime("%Y-%m-%d")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    return base_date


# ─── Step 1: フィード分割 ────────────────────────────────────────

def step1_split_feeds(base_date: str) -> bool:
    """フィードファイルを分野別に分割する。"""
    print(f"[{now_jst()}] Step 1: フィード分割...")

    split_script = SCRIPTS_DIR / "split-academic-feeds.py"
    result = subprocess.run(
        ["python3.12", str(split_script), "--date", base_date],
        capture_output=True, text=True,
    )

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"   {line}")

    if result.returncode != 0:
        print(f"   ⚠️  フィード分割失敗（Web検索のみで続行）")
        if result.stderr:
            print(f"   stderr: {result.stderr.strip()}")
        return False

    return True


# ─── Step 1.5: 既出URLリスト作成 ────────────────────────────────

def step1_5_build_existing_urls(base_date: str) -> Path | None:
    """過去3日分のレポートからURLを抽出して既出リストを作成する。"""
    print(f"[{now_jst()}] Step 1.5: 既出URLリスト作成...")

    dt = datetime.strptime(base_date, "%Y-%m-%d")
    urls: set[str] = set()

    for days_back in range(1, 4):
        past_date = (dt - timedelta(days=days_back)).strftime("%Y-%m-%d")
        report_path = OUTPUT_DIR / f"{past_date}_academic_trends.md"
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            # URL抽出（簡易）
            import re
            found_urls = re.findall(r'https?://[^\s)>\]]+', content)
            for url in found_urls:
                # 一覧ページは除外
                if url.rstrip("/").endswith(("/archive", "/feed", "/news", "/blog", "/research", "/latest")):
                    continue
                urls.add(url.rstrip("/"))

    if not urls:
        print(f"   ⏭️  既出URLなし")
        return None

    url_list_path = TMP_DIR / "existing_urls.txt"
    url_list_path.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")
    print(f"   ✅ {len(urls)}件のURLを抽出 → {url_list_path}")
    return url_list_path


# ─── Step 2: 分野ごとのextractor実行 ────────────────────────────

def step2_extract(
    field_configs: list[FieldConfig],
    base_date: str,
    existing_urls_path: Path | None,
    log_dir: Path,
    job_ctx: JobContext | None = None,
) -> dict[str, Path]:
    """各分野のextractorをAIコマンドで実行する。

    Returns:
        分野名 → 中間ファイルパスのマッピング
    """
    print(f"[{now_jst()}] Step 2: 分野ごとのsearcher実行...")
    intermediate_paths: dict[str, Path] = {}
    success = 0
    failed = 0

    for fc in field_configs:
        feed_path = TMP_DIR / f"{fc.name}_feed.md"
        output_path = TMP_DIR / f"{fc.name}_intermediate.md"
        log_file = log_dir / f"academic-searcher-{fc.name}.log"

        # フィードファイルの存在確認
        feed_info = ""
        if fc.has_feed and feed_path.exists():
            feed_info = f"フィードファイルパス: {feed_path}"
        else:
            feed_info = "フィードファイルパス: なし（Web検索のみ）"

        # 既出URLリスト
        url_info = ""
        if existing_urls_path and existing_urls_path.exists():
            url_info = f"既出URLリストファイル: {existing_urls_path}"

        # ジョブ: running に更新
        grandchild_name = f"academic-searcher-{fc.name}"
        if job_ctx:
            update_grandchild_job(job_ctx, grandchild_name, {
                "status": "running", "started_at": now_jst(),
            })

        prompt = (
            f"academic-trend-searcher として以下の分野を処理してください。\n"
            f"\n"
            f"分野名: {fc.name}\n"
            f"分野表示名: {fc.display_name}\n"
            f"対象日: {base_date}\n"
            f"中間出力ファイルパス: {output_path}\n"
            f"{feed_info}\n"
            f"{url_info}\n"
            f"\n"
            f"フィードファイルがあればreadFileで読み込み、Web検索で補完して、"
            f"中間出力ファイルに結果を書き出してください。"
        )

        print(f"[{now_jst()}]    🔄 {fc.name} ({fc.display_name}) searcher 実行中...")

        if run_ai_command(prompt, log_file, agent_name="academic-trend-searcher"):
            if output_path.exists():
                print(f"[{now_jst()}]    ✅ {fc.name} searcher 完了")
                intermediate_paths[fc.name] = output_path
                success += 1
                if job_ctx:
                    update_grandchild_job(job_ctx, grandchild_name, {
                        "status": "completed", "completed_at": now_jst(),
                    })
            else:
                print(f"[{now_jst()}]    ⚠️  {fc.name} searcher 完了（中間ファイル未生成）")
                failed += 1
                if job_ctx:
                    update_grandchild_job(job_ctx, grandchild_name, {
                        "status": "failed", "completed_at": now_jst(),
                        "error": "中間ファイル未生成",
                    })
        else:
            print(f"[{now_jst()}]    ❌ {fc.name} searcher 失敗（ログ: {log_file}）")
            failed += 1
            if job_ctx:
                update_grandchild_job(job_ctx, grandchild_name, {
                    "status": "failed", "completed_at": now_jst(),
                    "error": "AI command exit non-zero",
                })

    print(f"[{now_jst()}]    📊 searcher結果: ✅{success}件 / ❌{failed}件")
    return intermediate_paths


# ─── Step 3: 統合レポート作成 ────────────────────────────────────

def step3_report(
    intermediate_paths: dict[str, Path],
    base_date: str,
    log_dir: Path,
    job_ctx: JobContext | None = None,
) -> bool:
    """中間ファイルを統合レポートに結合する。"""
    print(f"[{now_jst()}] Step 3: 統合レポート作成...")

    if not intermediate_paths:
        print(f"[{now_jst()}]    ⚠️  中間ファイルなし（スキップ）")
        return False

    output_path = OUTPUT_DIR / f"{base_date}_academic_trends.md"
    input_files = ",".join(str(p) for p in intermediate_paths.values() if p.exists())

    if not input_files:
        print(f"[{now_jst()}]    ⚠️  有効な中間ファイルなし（スキップ）")
        return False

    # ジョブ: running に更新
    if job_ctx:
        update_grandchild_job(job_ctx, "academic-reporter", {
            "status": "running", "started_at": now_jst(),
        })

    merge_script = SCRIPTS_DIR / "merge-academic-intermediate-files.py"
    cmd = [
        "python3.12", str(merge_script),
        "--input", input_files,
        "--output", str(output_path),
        "--date", base_date,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and output_path.exists():
        print(f"[{now_jst()}]    ✅ 統合レポート完了: {output_path}")
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                print(f"[{now_jst()}]    {line}")

        # 注目論文選定 + 応用可能性サマリをAIコマンドで生成
        _generate_highlights(output_path, base_date, log_dir)

        if job_ctx:
            update_grandchild_job(job_ctx, "academic-reporter", {
                "status": "completed", "completed_at": now_jst(),
            })
        return True
    else:
        print(f"[{now_jst()}]    ❌ 統合レポート失敗")
        if result.stderr:
            print(f"[{now_jst()}]    stderr: {result.stderr.strip()}")
        if job_ctx:
            update_grandchild_job(job_ctx, "academic-reporter", {
                "status": "failed", "completed_at": now_jst(),
                "error": result.stderr.strip() or "merge script exit non-zero",
            })
        return False


def _generate_highlights(report_path: Path, base_date: str, log_dir: Path) -> None:
    """統合レポートに注目論文セクションと応用可能性サマリを追加する。"""
    log_file = log_dir / "academic-reporter.log"

    prompt = (
        f"以下のレポートファイルを読み込み、注目論文TOP3の選定と"
        f"応用可能性サマリテーブルを追加してください。\n"
        f"\n"
        f"レポートファイル: {report_path}\n"
        f"\n"
        f"処理手順:\n"
        f"1. レポートファイルをreadFileで読み込む\n"
        f"2. 全論文から最重要3件を選定し、概要を3〜5文に拡充する\n"
        f"3. 「## 🔥 注目論文・研究」セクションをレポート冒頭（# タイトルの直後）に挿入する\n"
        f"4. 「## 📊 当プロジェクトへの応用可能性サマリ」テーブルをレポート末尾に追加する\n"
        f"5. 修正したレポートを同じファイルに上書き保存する\n"
    )

    print(f"[{now_jst()}]    🔄 注目論文選定 + サマリ生成中...")
    if run_ai_command(prompt, log_file, agent_name="academic-trend-searcher"):
        print(f"[{now_jst()}]    ✅ 注目論文 + サマリ追加完了")
    else:
        print(f"[{now_jst()}]    ⚠️  注目論文選定失敗（レポート本体は生成済み）")


# ─── Step 4: クリーンアップ ──────────────────────────────────────

def step4_cleanup() -> None:
    """一時ファイルを削除する。"""
    print(f"[{now_jst()}] Step 4: クリーンアップ...")

    if TMP_DIR.exists():
        import shutil
        shutil.rmtree(TMP_DIR)
        print(f"   ✅ {TMP_DIR} 削除完了")


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    """パイプラインのメインエントリポイント。"""
    # 引数解析（--slack-channel / --slack-thread-ts はdispatch-router経由で渡される）
    slack_channel: str = ""
    slack_thread_ts: str = ""
    base_date_arg: str | None = None

    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--slack-channel" and i + 1 < len(argv):
            i += 1
            slack_channel = argv[i]
        elif arg == "--slack-thread-ts" and i + 1 < len(argv):
            i += 1
            slack_thread_ts = argv[i]
        else:
            base_date_arg = arg
        i += 1

    # ジョブコンテキスト読み込み
    job_ctx = load_job_context()

    # Step 0: 対象日決定 + ディレクトリ準備
    base_date = step0_prepare(base_date_arg)
    log_dir = HOME / "logs" / "jobs" / "scout_daily"
    log_dir.mkdir(parents=True, exist_ok=True)
    notify_log = log_dir / "academic-notify.log"

    print(f"[{now_jst()}] 📋 アカデミックトレンドスカウト パイプライン起動（基準日: {base_date}）")
    if job_ctx.enabled:
        print(f"[{now_jst()}]    ジョブ連携: 有効（parent_job_id={job_ctx.parent_job_id[:12]}...）")

    # dispatch経由で起動された場合: 元DMスレッドへ開始通知
    if slack_channel and slack_thread_ts:
        _notify_slack_reply(
            f"🚀 アカデミックトレンドスカウト開始（基準日: {base_date}）",
            slack_channel, slack_thread_ts, notify_log,
        )

    # Step 1: フィード分割
    step1_split_feeds(base_date)

    # Step 1.5: 既出URLリスト作成
    existing_urls_path = step1_5_build_existing_urls(base_date)

    # Step 2: 分野ごとのextractor実行
    intermediate_paths = step2_extract(
        FIELD_CONFIGS, base_date, existing_urls_path, log_dir,
        job_ctx=job_ctx if job_ctx.enabled else None,
    )

    # Step 3: 統合レポート作成
    report_ok = step3_report(
        intermediate_paths, base_date, log_dir,
        job_ctx=job_ctx if job_ctx.enabled else None,
    )

    # Step 4: クリーンアップ
    step4_cleanup()

    # 完了
    if report_ok:
        print(f"[{now_jst()}] ✅ アカデミックトレンドスカウト パイプライン完了（基準日: {base_date}）")
        # dispatch経由: 元スレッドへレポートと完了通知を返信
        if slack_channel and slack_thread_ts:
            output_path = OUTPUT_DIR / f"{base_date}_academic_trends.md"
            if output_path.exists():
                run_slack_notify(output_path, notify_log, channel=slack_channel, thread=slack_thread_ts)
            _notify_slack_reply(
                f"✅ アカデミックトレンドスカウト完了（基準日: {base_date}）",
                slack_channel, slack_thread_ts, notify_log,
            )
        sys.exit(0)
    else:
        print(f"[{now_jst()}] ⚠️  アカデミックトレンドスカウト パイプライン一部失敗（基準日: {base_date}）")
        # dispatch経由: 元スレッドへ失敗通知
        if slack_channel and slack_thread_ts:
            _notify_slack_reply(
                f"⚠️ アカデミックトレンドスカウト一部失敗（基準日: {base_date}）",
                slack_channel, slack_thread_ts, notify_log,
            )
        sys.exit(1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
