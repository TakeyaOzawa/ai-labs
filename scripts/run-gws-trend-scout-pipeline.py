#!/usr/bin/env python3.12
"""
run-gws-trend-scout-pipeline: GWSトレンドスカウトのパイプライン化実行

目的:
    gws-trend-scoutの単一コンテキスト実行を廃止し、種別ごとに独立した
    kiro-cliプロセスで実行する。100件超のメタデータでもコンテキスト圧迫なく
    処理できるようにする。

使い方:
    python3.12 scripts/run-gws-trend-scout-pipeline.py [基準日]
    python3.12 scripts/run-gws-trend-scout-pipeline.py 2026-05-08

出力: Documents/works/scout_histories/gws_trends/daily/{date}_gws_daily.md
依存: python3.12, gws CLI, kiro-cli, filter-gws-drive-metadata.py
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
TMP_DIR = HOME / "Documents" / "works" / "scout_histories" / "gws_trends" / "daily" / "tmp"
OUTPUT_BASE = HOME / "Documents" / "works" / "scout_histories" / "gws_trends" / "daily"
FILTER_SCRIPT = SCRIPTS_DIR / "filter-gws-drive-metadata.py"
OWNER_EMAIL = "takeya_ozawa@nyle.co.jp"
INTERFACES_FILE = "~/.shared-ai/interfaces/gws-trend-report-output.md"


# ─── 種別パラメータ定義 ──────────────────────────────────────────

@dataclass
class TypeConfig:
    """種別ごとのパラメータ定義。"""

    name: str           # docs / slides / sheets / forms / pdf
    icon: str           # 📄 / 📊 / 📈 / 📝 / 📎
    mime: str           # MIME type
    drill_command: str  # 深掘りコマンドテンプレート（{ID}をドキュメントIDに置換）
    top_count: int      # 深掘り上位件数


TYPE_CONFIGS = [
    TypeConfig(
        "docs", "📄", "application/vnd.google-apps.document",
        "gws docs documents get --params '{\"documentId\": \"{ID}\"}'"
        " | python3.12 ~/scripts/extract-gws-doc-text.py",
        10,
    ),
    TypeConfig(
        "slides", "📊", "application/vnd.google-apps.presentation",
        "gws slides presentations get --params '{\"presentationId\": \"{ID}\"}'"
        " | python3.12 ~/scripts/extract-gws-slides-text.py",
        10,
    ),
    TypeConfig(
        "sheets", "📈", "application/vnd.google-apps.spreadsheet",
        "gws sheets spreadsheets get --params '{\"spreadsheetId\": \"{ID}\"}'"
        " | head -c 8000",
        10,
    ),
    TypeConfig(
        "forms", "📝", "application/vnd.google-apps.form",
        "gws forms forms get --params '{\"formId\": \"{ID}\"}'"
        " | head -c 8000",
        5,
    ),
    TypeConfig(
        "pdf", "📎", "application/pdf",
        "",
        0,
    ),
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
    # ジョブファイルからjob_nameでIDを再帰検索
    cmd = [
        "python3.12", str(SCRIPTS_DIR / "find-job.py"),
        "--pipeline", "daily",
        "--job-name", job_name,
        "--limit", "1",
    ]
    # find-job.pyはジョブファイルを自動検出するが、直接ファイルを操作する方が確実
    # update-job.pyの再帰検索を利用
    try:
        with open(ctx.job_file, encoding="utf-8") as f:
            data = json.load(f)
        # 再帰検索でjob_idを取得
        job_id = _find_grandchild_id(data.get("child_jobs", []), job_name)
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


def _find_grandchild_id(jobs: list[dict], job_name: str) -> str:
    """ジョブツリーを再帰的に探索し、指定名のジョブIDを返す。"""
    for job in jobs:
        if job.get("job_name") == job_name:
            return job.get("job_id", "")
        found = _find_grandchild_id(job.get("child_jobs", []), job_name)
        if found:
            return found
    return ""


def run_kiro_cli(prompt: str, log_file: Path, agent_name: str) -> bool:
    """kiro-cliを実行し、成功/失敗を返す。"""
    cmd = [
        "kiro-cli", "chat",
        "--trust-all-tools", "--no-interactive",
        "--agent", agent_name,
        prompt,
    ]
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return result.returncode == 0


def build_drive_query(mime: str, start_utc: str, end_utc: str) -> str:
    """Drive APIクエリ文字列を構築する。"""
    time_filter = (
        f"((modifiedTime > '{start_utc}' and modifiedTime < '{end_utc}') "
        f"or (createdTime > '{start_utc}' and createdTime < '{end_utc}'))"
    )
    return (
        f"mimeType = '{mime}' and trashed = false and {time_filter}"
    )


# ─── Step 0: 対象日決定 + ディレクトリ準備 ───────────────────────

def step0_prepare(base_date_str: str | None) -> tuple[str, str, str]:
    """対象日を決定し、ディレクトリを準備する。

    Returns:
        (base_date, start_utc, end_utc)
    """
    if base_date_str:
        base_date = base_date_str
    else:
        yesterday = datetime.now(tz=JST) - timedelta(days=1)
        base_date = yesterday.strftime("%Y-%m-%d")

    # JST日付 → UTC範囲に変換
    # base_date の 00:00 JST = 前日 15:00 UTC
    # base_date の 23:59:59 JST = 当日 14:59:59 UTC
    dt = datetime.strptime(base_date, "%Y-%m-%d")
    start_utc = (dt - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_utc = (dt + timedelta(hours=15) - timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # ディレクトリ準備
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    return base_date, start_utc, end_utc


# ─── Step 1: メタデータ一括取得 ──────────────────────────────────

def step1_fetch_metadata(
    type_configs: list[TypeConfig], start_utc: str, end_utc: str,
) -> dict[str, Path]:
    """各種別のメタデータをNDJSONで取得する。

    Returns:
        種別名 → NDJSONファイルパスのマッピング
    """
    print(f"[{now_jst()}] Step 1: メタデータ一括取得...")
    ndjson_paths: dict[str, Path] = {}

    for tc in type_configs:
        ndjson_path = TMP_DIR / f"{tc.name}_metadata.ndjson"
        query = build_drive_query(tc.mime, start_utc, end_utc)

        params = json.dumps({
            "q": query,
            "fields": (
                "nextPageToken,files(id,name,mimeType,modifiedTime,createdTime,"
                "owners,lastModifyingUser,shared,sharingUser,webViewLink)"
            ),
            "pageSize": 100,
            "orderBy": "modifiedTime desc",
            "includeItemsFromAllDrives": True,
            "supportsAllDrives": True,
        }, ensure_ascii=False)

        cmd = [
            "gws", "drive", "files", "list",
            "--page-all", "--page-limit", "50",
            "--params", params,
        ]

        with open(ndjson_path, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd, stdout=f, stderr=subprocess.DEVNULL,
            )

        status = "✅" if result.returncode == 0 else "⚠️"
        print(f"   {status} {tc.name}: {ndjson_path}")
        ndjson_paths[tc.name] = ndjson_path

    return ndjson_paths


# ─── Step 2: フィルタリング ──────────────────────────────────────

def step2_filter(
    type_configs: list[TypeConfig], ndjson_paths: dict[str, Path],
) -> dict[str, Path]:
    """各種別のメタデータをフィルタリングする。

    Returns:
        種別名 → フィルタ結果JSONファイルパスのマッピング
    """
    print(f"[{now_jst()}] Step 2: フィルタリング...")
    filtered_paths: dict[str, Path] = {}

    for tc in type_configs:
        ndjson_path = ndjson_paths.get(tc.name)
        if not ndjson_path or not ndjson_path.exists():
            print(f"   ⏭️  {tc.name}: メタデータなし（スキップ）")
            continue

        filtered_path = TMP_DIR / f"{tc.name}_filtered.json"

        cmd = [
            "python3.12", str(FILTER_SCRIPT),
            "--input", str(ndjson_path),
            "--output", str(filtered_path),
            "--owner-email", OWNER_EMAIL,
            "--top", str(tc.top_count),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        status = "✅" if result.returncode == 0 else "⚠️"
        print(f"   {status} {tc.name}: {filtered_path}")
        filtered_paths[tc.name] = filtered_path

    return filtered_paths


# ─── Step 3: 種別ごとの深掘り＋中間ファイル作成 ─────────────────

def step3_collect(
    type_configs: list[TypeConfig],
    filtered_paths: dict[str, Path],
    base_date: str,
    log_dir: Path,
    job_ctx: JobContext | None = None,
) -> dict[str, Path]:
    """各種別のextractorをkiro-cliで実行する。

    Returns:
        種別名 → 中間ファイルパスのマッピング
    """
    print(f"[{now_jst()}] Step 3: 種別ごとの深掘り＋中間ファイル作成...")
    intermediate_paths: dict[str, Path] = {}
    success = 0
    failed = 0

    for tc in type_configs:
        filtered_path = filtered_paths.get(tc.name)
        if not filtered_path or not filtered_path.exists():
            print(f"   ⏭️  {tc.name}: フィルタ結果なし（スキップ）")
            continue

        # フィルタ結果が空かチェック
        try:
            with open(filtered_path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("summary", {}).get("filtered_count", 0) == 0:
                print(f"   ⏭️  {tc.name}: フィルタ後0件（スキップ）")
                continue
        except (json.JSONDecodeError, OSError):
            print(f"   ⚠️  {tc.name}: フィルタ結果読み込みエラー（スキップ）")
            continue

        grandchild_name = f"gws-extractor-{tc.name}"
        output_path = TMP_DIR / f"{tc.name}.md"
        log_file = log_dir / f"extractor-{tc.name}.log"

        drill_cmd = tc.drill_command if tc.drill_command else "なし"

        # ジョブ: running に更新
        if job_ctx:
            update_grandchild_job(job_ctx, grandchild_name, {
                "status": "running", "started_at": now_jst(),
            })

        prompt = (
            f"gws-trend-extractor として以下の種別を処理してください。\n"
            f"\n"
            f"種別: {tc.name}\n"
            f"アイコン: {tc.icon}\n"
            f"対象期間開始: {base_date}\n"
            f"対象期間終了: {base_date}\n"
            f"中間出力ファイル: {output_path}\n"
            f"深掘りコマンド: {drill_cmd}\n"
            f"深掘り上位件数: {tc.top_count}\n"
            f"フィルタ結果ファイル: {filtered_path}\n"
            f"\n"
            f"フィルタ結果ファイルを readFile で読み込み、"
            f"関連度判定・カテゴリ分類・深掘り・中間ファイル出力を行ってください。"
        )

        print(f"[{now_jst()}]    🔄 {tc.name} extractor 実行中...")

        if run_kiro_cli(prompt, log_file, agent_name="gws-trend-extractor"):
            if output_path.exists():
                print(f"[{now_jst()}]    ✅ {tc.name} extractor 完了")
                intermediate_paths[tc.name] = output_path
                success += 1
                if job_ctx:
                    update_grandchild_job(job_ctx, grandchild_name, {
                        "status": "completed", "completed_at": now_jst(),
                    })
            else:
                print(f"[{now_jst()}]    ⚠️  {tc.name} extractor 完了（中間ファイル未生成）")
                failed += 1
                if job_ctx:
                    update_grandchild_job(job_ctx, grandchild_name, {
                        "status": "failed", "completed_at": now_jst(),
                        "error": "中間ファイル未生成",
                    })
        else:
            print(f"[{now_jst()}]    ❌ {tc.name} extractor 失敗（ログ: {log_file}）")
            failed += 1
            if job_ctx:
                update_grandchild_job(job_ctx, grandchild_name, {
                    "status": "failed", "completed_at": now_jst(),
                    "error": "kiro-cli exit non-zero",
                })

    print(f"[{now_jst()}]    📊 extractor結果: ✅{success}件 / ❌{failed}件")
    return intermediate_paths


# ─── Step 4: 統合レポート作成 ────────────────────────────────────

def step4_report(
    intermediate_paths: dict[str, Path],
    base_date: str,
    log_dir: Path,
    job_ctx: JobContext | None = None,
) -> bool:
    """markdown-reporterで統合レポートを作成する。"""
    print(f"[{now_jst()}] Step 4: 統合レポート作成...")

    if not intermediate_paths:
        print(f"[{now_jst()}]    ⚠️  中間ファイルなし（スキップ）")
        return False

    output_path = OUTPUT_BASE / f"{base_date}_gws_daily.md"
    input_files = ", ".join(str(p) for p in intermediate_paths.values() if p.exists())

    if not input_files:
        print(f"[{now_jst()}]    ⚠️  有効な中間ファイルなし（スキップ）")
        return False

    log_file = log_dir / "reporter.log"

    # ジョブ: running に更新
    if job_ctx:
        update_grandchild_job(job_ctx, "markdown-reporter", {
            "status": "running", "started_at": now_jst(),
        })

    prompt = (
        f"入力ファイル: {input_files}\n"
        f"出力先: {output_path}\n"
        f"フォーマット指示ファイル: {INTERFACES_FILE}\n"
        f"\n"
        f"対象期間: {base_date}\n"
        f"\n"
        f"【重要: コンテキスト節約ルール】\n"
        f"完了時は以下の形式のみで報告すること。"
        f"レポート全文やファイル内容は絶対に返さないこと:\n"
        f"✅ 統合レポート完了\n"
        f"- 出力: {{ファイルパス}}\n"
        f"- ドキュメント総数: {{N}}件"
    )

    if run_kiro_cli(prompt, log_file, agent_name="markdown-reporter"):
        print(f"[{now_jst()}]    ✅ 統合レポート完了: {output_path}")
        if job_ctx:
            update_grandchild_job(job_ctx, "markdown-reporter", {
                "status": "completed", "completed_at": now_jst(),
            })
        return True
    else:
        print(f"[{now_jst()}]    ❌ 統合レポート失敗（ログ: {log_file}）")
        if job_ctx:
            update_grandchild_job(job_ctx, "markdown-reporter", {
                "status": "failed", "completed_at": now_jst(),
                "error": "kiro-cli exit non-zero",
            })
        return False


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    """パイプラインのメインエントリポイント。"""
    # 引数解析
    base_date_arg: str | None = None
    if len(sys.argv) > 1:
        base_date_arg = sys.argv[1]

    # ジョブコンテキスト読み込み（親パイプラインから環境変数経由）
    job_ctx = load_job_context()

    # Step 0: 対象日決定 + ディレクトリ準備
    base_date, start_utc, end_utc = step0_prepare(base_date_arg)
    log_dir = HOME / "logs" / "jobs" / "scout_daily"
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{now_jst()}] 📋 GWSトレンドスカウト パイプライン起動（基準日: {base_date}）")
    print(f"[{now_jst()}]    UTC範囲: {start_utc} 〜 {end_utc}")
    if job_ctx.enabled:
        print(f"[{now_jst()}]    ジョブ連携: 有効（parent_job_id={job_ctx.parent_job_id[:12]}...）")

    # Step 1: メタデータ一括取得
    ndjson_paths = step1_fetch_metadata(TYPE_CONFIGS, start_utc, end_utc)

    # Step 2: フィルタリング
    filtered_paths = step2_filter(TYPE_CONFIGS, ndjson_paths)

    # Step 3: 種別ごとの深掘り＋中間ファイル作成
    intermediate_paths = step3_collect(
        TYPE_CONFIGS, filtered_paths, base_date, log_dir,
        job_ctx=job_ctx if job_ctx.enabled else None,
    )

    # Step 4: 統合レポート作成
    report_ok = step4_report(
        intermediate_paths, base_date, log_dir,
        job_ctx=job_ctx if job_ctx.enabled else None,
    )

    # Step 5: 完了
    if report_ok:
        print(f"[{now_jst()}] ✅ GWSトレンドスカウト パイプライン完了（基準日: {base_date}）")
        sys.exit(0)
    else:
        print(f"[{now_jst()}] ⚠️  GWSトレンドスカウト パイプライン一部失敗（基準日: {base_date}）")
        sys.exit(1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
