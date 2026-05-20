#!/usr/bin/env python3.12
"""
radio-pipeline-watcher: ラジオパイプラインファイルウォッチャー

目的:
    ジョブファイルを5分おきにポーリングし、
    pendingの子ジョブ（transcription, summarization, notification）を
    順次実行する。

使い方:
    python3.12 ~/scripts/jobs/radio-pipeline-watcher.py --once
    python3.12 ~/scripts/jobs/radio-pipeline-watcher.py --watch

出力: ジョブファイル更新、文字起こし結果、要約MD、Slack通知
依存: docker compose, invoke-agent.py, notify-slack.py, file_organizer.py
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import load_env
from logger import PipelineLogger
from pipeline_engine import start_caffeinate, stop_caffeinate, now_jst

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
PIPELINE_DIR = HOME / "tools" / "radio_content_pipeline"
JOB_DIR = HOME / "Documents" / "works" / "jobs" / "radio_pipeline"
LOG_DIR = HOME / "logs" / "jobs" / "radio_content_pipeline_watcher"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent

NOTIFY_SCRIPT = SCRIPTS_DIR / "slack" / "notify-slack.py"
if not NOTIFY_SCRIPT.exists():
    NOTIFY_SCRIPT = SCRIPTS_DIR / "notify-slack.py"

INVOKE_AGENT_SCRIPT = SCRIPTS_DIR / "ai" / "invoke-agent.py"
if not INVOKE_AGENT_SCRIPT.exists():
    INVOKE_AGENT_SCRIPT = SCRIPTS_DIR / "invoke-agent.py"

FILE_ORGANIZER_SCRIPT = PIPELINE_DIR / "src" / "file_organizer.py"

POLL_INTERVAL = 300  # 5分
TIMEOUT_HOURS = 2  # running状態のタイムアウト

# ジョブ処理順序（依存関係）
JOB_ORDER = ["recording", "transcription", "summarization", "notification"]


# ─── ジョブファイル操作 ───────────────────────────────────────────

def find_latest_job_file() -> Path | None:
    """最新のジョブファイルを返す。"""
    if not JOB_DIR.exists():
        return None
    json_files = sorted(JOB_DIR.glob("*.json"))
    return json_files[-1] if json_files else None


def load_job_data(job_file: Path) -> dict | None:
    """ジョブファイルを読み込む。"""
    try:
        with open(job_file, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_job_data(job_file: Path, data: dict) -> None:
    """ジョブファイルを書き込む。"""
    job_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_child_status(
    job_file: Path,
    data: dict,
    job_id: str,
    updates: dict,
) -> None:
    """子ジョブのステータスを更新してファイルに書き戻す。"""
    for child in data.get("child_jobs", []):
        if child.get("job_id") == job_id:
            child.update(updates)
            break
    data["updated_at"] = now_jst()
    save_job_data(job_file, data)


def update_parent_status(job_file: Path, data: dict, status: str) -> None:
    """親ジョブのステータスを更新する。"""
    data["status"] = status
    data["updated_at"] = now_jst()
    if status in ("completed", "failed"):
        data["completed_at"] = now_jst()
    save_job_data(job_file, data)


# ─── 依存関係チェック ────────────────────────────────────────────

def get_program_prefix(child: dict) -> str:
    """子ジョブから番組識別プレフィックスを抽出する。

    argsのfileフィールドまたはprogram+stationから、
    局名_番組名_日付 のプレフィックスを生成する。
    """
    args = child.get("args", {})

    # file フィールドからプレフィックスを抽出（拡張子と_summary部分を除去）
    file_name = args.get("file", "")
    if file_name:
        # 例: "TBS_空気階段の踊り場_20260519.m4a" → "TBS_空気階段の踊り場_20260519"
        # 例: "TBS_空気階段の踊り場_20260519.json" → "TBS_空気階段の踊り場_20260519"
        # 例: "TBS_空気階段の踊り場_20260519_summary.md" → "TBS_空気階段の踊り場_20260519"
        base = file_name.rsplit(".", 1)[0]  # 拡張子除去
        base = base.removesuffix("_summary")
        return base

    # program + station から生成
    program = args.get("program", "")
    station = args.get("station", "")
    if program and station:
        return f"{station}_{program}"

    return child.get("job_id", "")


def get_preceding_job_name(job_name: str) -> str | None:
    """指定ジョブの前段ジョブ名を返す。"""
    try:
        idx = JOB_ORDER.index(job_name)
        return JOB_ORDER[idx - 1] if idx > 0 else None
    except ValueError:
        return None


def is_preceding_completed(child_jobs: list[dict], target: dict) -> bool:
    """対象ジョブの前段が完了しているか判定する。

    同じ番組の前段ジョブが completed でないと処理しない。
    番組の照合は前方一致で行う（recordingはargs.program/stationから生成されるため
    日付を含まないが、transcription以降はargs.fileから日付付きで生成される）。
    """
    target_name = target.get("job_name", "")
    preceding_name = get_preceding_job_name(target_name)

    # 前段がない（recordingの場合）→ 常にTrue
    if preceding_name is None:
        return True

    target_prefix = get_program_prefix(target)

    # 同じ番組の前段ジョブを探す（前方一致で照合）
    for child in child_jobs:
        if child.get("job_name") != preceding_name:
            continue
        child_prefix = get_program_prefix(child)
        # 完全一致 or 前方一致（短い方が長い方の先頭に含まれる）
        if child_prefix == target_prefix or target_prefix.startswith(child_prefix):
            return child.get("status") == "completed"

    # 前段ジョブが見つからない場合は処理しない
    return False


def has_running_job_of_type(child_jobs: list[dict], job_name: str) -> bool:
    """指定タイプのrunning中ジョブが存在するか判定する（二重起動防止）。"""
    for child in child_jobs:
        if child.get("job_name") == job_name and child.get("status") == "running":
            return True
    return False


# ─── タイムアウト処理 ────────────────────────────────────────────

def check_and_timeout_running_jobs(
    job_file: Path,
    data: dict,
    plogger: PipelineLogger,
) -> None:
    """running状態が2時間以上経過したジョブをfailedに更新する。"""
    now = datetime.now(tz=JST)
    timeout_delta = timedelta(hours=TIMEOUT_HOURS)

    for child in data.get("child_jobs", []):
        if child.get("status") != "running":
            continue

        started_at = child.get("started_at")
        if not started_at:
            continue

        try:
            started = datetime.fromisoformat(started_at)
            if now - started > timeout_delta:
                job_id = child.get("job_id", "unknown")
                job_name = child.get("job_name", "unknown")
                plogger.warning(
                    f"タイムアウト: {job_name} (id={job_id}) "
                    f"started_at={started_at} → failed に更新"
                )
                update_child_status(job_file, data, job_id, {
                    "status": "failed",
                    "error": f"timeout after {TIMEOUT_HOURS}h",
                    "updated_at": now_jst(),
                })
        except (ValueError, TypeError):
            continue


# ─── ジョブ実行 ──────────────────────────────────────────────────

def execute_transcription(args: dict, log_file: Path, plogger: PipelineLogger) -> tuple[bool, str]:
    """文字起こしを実行する。"""
    file_name = args.get("file", "")
    if not file_name:
        return False, "file arg is empty"

    file_path = f"/data/recordings/{file_name}"
    cmd = [
        "docker", "compose", "run", "--rm",
        "transcriber", "python3", "src/transcriber.py", "--file", file_path,
    ]

    plogger.info(f"   実行: docker compose run --rm transcriber ... --file {file_path}")

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=f,
                cwd=str(PIPELINE_DIR),
                text=True,
                timeout=7200,  # 2時間タイムアウト
            )
        if result.returncode == 0:
            return True, result.stdout
        return False, f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "process timeout (2h)"
    except OSError as e:
        return False, str(e)


def extract_full_text(transcript_path: Path) -> str:
    """文字起こしJSONからfull_textを抽出する。"""
    if not transcript_path.exists():
        return ""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("full_text", "")
    except (json.JSONDecodeError, OSError):
        return ""


def execute_summarization(args: dict, log_file: Path, plogger: PipelineLogger) -> tuple[bool, str]:
    """要約を実行する。

    invoke-agent.py にJSONファイルパスを渡し、エージェントが
    Step 1（メタデータ+full_text抽出）→ Step 4（要約作成）を実行する。
    出力先はエージェントが自動決定: data/summaries/{filename}_summary.md
    """
    file_name = args.get("file", "")
    if not file_name:
        return False, "file arg is empty"

    transcript_path = PIPELINE_DIR / "data" / "transcripts" / file_name

    if not transcript_path.exists():
        return False, f"transcript not found: {transcript_path}"

    # invoke-agent.py で要約実行
    # エージェントにJSONファイルパスを渡す（エージェントがStep 1でfull_textを抽出する）
    prompt = f"{transcript_path} を要約してください"

    cmd = [
        "python3.12", str(INVOKE_AGENT_SCRIPT),
        "--agent", "radio-transcript-summarizer",
        "--prompt", prompt,
    ]

    plogger.info(f"   実行: invoke-agent.py --agent radio-transcript-summarizer (入力: {file_name})")

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=f,
                text=True,
                timeout=600,  # 10分タイムアウト
            )
        if result.returncode == 0:
            return True, result.stdout
        return False, f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "process timeout (10min)"
    except OSError as e:
        return False, str(e)


def execute_notification(args: dict, log_file: Path, plogger: PipelineLogger) -> tuple[bool, str]:
    """Slack通知 + ファイル配置を実行する。"""
    file_name = args.get("file", "")
    if not file_name:
        return False, "file arg is empty"

    summary_path = PIPELINE_DIR / "data" / "summaries" / file_name

    if not summary_path.exists():
        return False, f"summary not found: {summary_path}"

    # 1. Slack通知（compactスレッドにまとめる）
    plogger.info(f"   実行: notify-slack.py --file {summary_path} --thread compact")
    cmd = ["python3.12", str(NOTIFY_SCRIPT), "--file", str(summary_path), "--thread", "compact"]

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
        if result.returncode != 0:
            return False, f"notify-slack.py exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "notify-slack.py timeout"
    except OSError as e:
        return False, f"notify-slack.py error: {e}"

    # 2. ファイル配置（file_organizer.py）— 存在する場合のみ実行
    if FILE_ORGANIZER_SCRIPT.exists():
        plogger.info(f"   実行: file_organizer.py --file {summary_path}")
        cmd = ["python3.12", str(FILE_ORGANIZER_SCRIPT), "--file", str(summary_path)]

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                )
            if result.returncode != 0:
                plogger.warning(f"   file_organizer.py exit code {result.returncode}（続行）")
        except subprocess.TimeoutExpired:
            plogger.warning("   file_organizer.py timeout（続行）")
        except OSError as e:
            plogger.warning(f"   file_organizer.py error: {e}（続行）")
    else:
        plogger.info("   file_organizer.py 未作成 — スキップ")

    return True, "notification completed"


# ─── ジョブ実行ディスパッチ ───────────────────────────────────────

# ウォッチャーが処理する子ジョブ名のマッピング
EXECUTORS: dict[str, callable] = {}


def dispatch_job(
    child: dict,
    job_file: Path,
    data: dict,
    plogger: PipelineLogger,
) -> bool:
    """子ジョブを実行する。

    Returns:
        True: 処理成功, False: 処理失敗
    """
    job_name = child.get("job_name", "")
    job_id = child.get("job_id", "unknown")
    args = child.get("args", {})

    # recordingはウォッチャーでは扱わない
    if job_name == "recording":
        return False

    plogger.info(f"ジョブ実行開始: {job_name} (id={job_id})")

    # ステータスを running に更新
    update_child_status(job_file, data, job_id, {
        "status": "running",
        "started_at": now_jst(),
        "updated_at": now_jst(),
    })

    # ログファイル
    log_file = plogger.get_log_file(f"{job_name}-{job_id[:8]}")

    # caffeinate 開始（処理中のみスリープ防止）
    cafe_pid = start_caffeinate()

    try:
        if job_name == "transcription":
            ok, output = execute_transcription(args, log_file, plogger)
        elif job_name == "summarization":
            ok, output = execute_summarization(args, log_file, plogger)
        elif job_name == "notification":
            ok, output = execute_notification(args, log_file, plogger)
        else:
            plogger.warning(f"   未知のジョブタイプ: {job_name}")
            ok, output = False, f"unknown job_name: {job_name}"
    finally:
        stop_caffeinate(cafe_pid)

    # ステータス更新
    if ok:
        plogger.info(f"   ✅ {job_name} 完了 (id={job_id})")
        update_child_status(job_file, data, job_id, {
            "status": "completed",
            "completed_at": now_jst(),
            "updated_at": now_jst(),
        })
    else:
        plogger.error(f"   ❌ {job_name} 失敗 (id={job_id}): {output}")
        update_child_status(job_file, data, job_id, {
            "status": "failed",
            "error": output[:200],
            "updated_at": now_jst(),
        })

    return ok


# ─── 親ジョブ完了判定 ────────────────────────────────────────────

def check_all_completed(data: dict) -> bool:
    """全子ジョブが completed かどうか判定する。"""
    child_jobs = data.get("child_jobs", [])
    if not child_jobs:
        return False
    return all(c.get("status") == "completed" for c in child_jobs)


def check_any_failed(data: dict) -> bool:
    """いずれかの子ジョブが failed かどうか判定する（リトライ不可の最終判定用）。"""
    # 全ジョブが completed or failed で、かつ failed が存在する場合
    child_jobs = data.get("child_jobs", [])
    if not child_jobs:
        return False
    all_terminal = all(c.get("status") in ("completed", "failed") for c in child_jobs)
    any_failed = any(c.get("status") == "failed" for c in child_jobs)
    return all_terminal and any_failed


# ─── メインスキャンループ ────────────────────────────────────────

def scan_and_process(plogger: PipelineLogger) -> int:
    """ジョブファイルをスキャンし、pendingジョブを順次処理する。

    Returns:
        処理したジョブ数
    """
    job_file = find_latest_job_file()
    if job_file is None:
        plogger.debug("ジョブファイルなし")
        return 0

    data = load_job_data(job_file)
    if data is None:
        plogger.warning(f"ジョブファイル読み込み失敗: {job_file}")
        return 0

    # 親ジョブが既に完了/失敗していたらスキップ
    parent_status = data.get("status", "")
    if parent_status in ("completed", "failed"):
        plogger.debug(f"親ジョブは既に {parent_status}")
        return 0

    child_jobs = data.get("child_jobs", [])
    if not child_jobs:
        return 0

    # タイムアウトチェック
    check_and_timeout_running_jobs(job_file, data, plogger)

    # pendingジョブを依存関係順に処理
    processed = 0

    for job_name in JOB_ORDER:
        # recordingはウォッチャーでは扱わない
        if job_name == "recording":
            continue

        # 同種のrunningジョブがあれば、そのタイプはスキップ（二重起動防止）
        if has_running_job_of_type(child_jobs, job_name):
            plogger.debug(f"   {job_name}: running中のジョブあり — スキップ")
            continue

        # pendingの子ジョブを探す（同じ番組の依存関係順）
        for child in child_jobs:
            if child.get("job_name") != job_name:
                continue
            if child.get("status") != "pending":
                continue

            # 前段が完了しているか確認
            if not is_preceding_completed(child_jobs, child):
                continue

            # 実行
            ok = dispatch_job(child, job_file, data, plogger)
            processed += 1

            # 1件ずつ順次処理（並行実行しない）
            # 処理後にデータを再読み込みして最新状態を確認
            data = load_job_data(job_file)
            if data is None:
                return processed
            child_jobs = data.get("child_jobs", [])

            # 同種のジョブは1件処理したら次のタイプへ
            break

    # 全子ジョブ完了チェック → 親ジョブも完了に
    data = load_job_data(job_file)
    if data is not None:
        if check_all_completed(data):
            plogger.info("🎉 全子ジョブ完了 → 親ジョブを completed に更新")
            update_parent_status(job_file, data, "completed")

    return processed


# ─── エントリポイント ────────────────────────────────────────────

def run_once(plogger: PipelineLogger) -> None:
    """1回スキャンして処理する。"""
    plogger.info("radio-pipeline-watcher: 1回スキャン開始")
    processed = scan_and_process(plogger)
    plogger.info(f"radio-pipeline-watcher: スキャン完了（{processed}件処理）")


def run_watch(plogger: PipelineLogger) -> None:
    """5分おきにポーリングする常駐モード。"""
    plogger.info(f"radio-pipeline-watcher: watchモード開始（{POLL_INTERVAL}秒間隔）")

    try:
        while True:
            try:
                processed = scan_and_process(plogger)
                if processed > 0:
                    plogger.info(f"   ポーリング: {processed}件処理")
            except Exception as e:
                plogger.error(f"スキャン中にエラー: {e}")

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        plogger.info("radio-pipeline-watcher: 終了（KeyboardInterrupt）")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ラジオパイプラインファイルウォッチャー"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="1回スキャンして終了")
    group.add_argument("--watch", action="store_true", help="5分おきポーリング常駐")
    args = parser.parse_args()

    # 環境変数ロード
    load_env()

    # ログ初期化
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plogger = PipelineLogger(
        "radio-pipeline-watcher",
        log_dir=LOG_DIR,
        max_lines=1000,
        keep_lines=200,
        agent_max_lines=500,
        agent_keep_lines=100,
    )
    plogger.rotate_all()

    if args.once:
        run_once(plogger)
    else:
        run_watch(plogger)


if __name__ == "__main__":
    main()
