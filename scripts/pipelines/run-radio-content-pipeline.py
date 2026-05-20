#!/usr/bin/env python3.12
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))  # noqa: E402
"""
run-radio-content-pipeline: ラジオ録音パイプライン日次トリガー

目的:
    毎朝6時にcron/LaunchAgentから起動され、
    番組検索→録音を実行する。文字起こし以降はウォッチャーに委譲。

使い方:
    python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py
    python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py --dry-run
    python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py --no-job-file

出力: ジョブファイル（~/Documents/works/jobs/radio_pipeline/）
依存: docker compose, notify-slack.py
"""

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import load_env
from logger import PipelineLogger
from pipeline_engine import (
    HOME,
    SCRIPTS_DIR,
    start_caffeinate,
    stop_caffeinate,
    now_jst,
    generate_id,
)

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
PIPELINE_DIR = HOME / "tools" / "radio_content_pipeline"
JOB_DIR = HOME / "Documents" / "works" / "jobs" / "radio_pipeline"
LOG_DIR = HOME / "logs" / "jobs" / "radio_content_pipeline"

PIPELINE_NAME = "radio_pipeline"
RECORDINGS_RETENTION_DAYS = 30

# ホスト側の state ディレクトリ（コンテナ内 /app/state にマウントされる）
STATE_DIR = PIPELINE_DIR / "state"
RECORDING_TASKS_FILE = STATE_DIR / "recording-tasks.json"


# ─── Slack通知 ───────────────────────────────────────────────────

def _notify_slack_text(text: str, log_file: Path, channel: str = "", thread: str = "") -> bool:
    """Slackにテキスト通知を送信する。"""
    notify_script = SCRIPTS_DIR / "slack" / "notify-slack.py"
    if not notify_script.exists():
        notify_script = SCRIPTS_DIR / "notify-slack.py"
    if not notify_script.exists():
        return False

    cmd = ["python3.12", str(notify_script), "--text", text]
    if channel:
        cmd.extend(["--channel", channel])
    if thread:
        cmd.extend(["--thread", thread])

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        return result.returncode == 0
    except OSError:
        return False


# ─── Docker Compose 実行 ─────────────────────────────────────────

def _docker_compose_run(
    service: str,
    command: list[str],
    log_file: Path,
    timeout: int = 0,
) -> tuple[bool, str]:
    """docker compose run --rm を実行する。

    Args:
        service: サービス名（recorder / transcriber）
        command: 実行コマンド
        log_file: stderrログ出力先
        timeout: タイムアウト秒（0=無制限）

    Returns:
        (成功フラグ, stdout出力 or エラーメッセージ)
    """
    cmd = [
        "docker", "compose", "run", "--rm",
        service, *command,
    ]
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=f,
                cwd=str(PIPELINE_DIR),
                text=True,
                timeout=timeout if timeout > 0 else None,
            )
        if result.returncode == 0:
            return True, result.stdout
        return False, f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timeout ({timeout}s)"
    except OSError as e:
        return False, f"OSError: {e}"


# ─── クリーンアップ ───────────────────────────────────────────────

def _cleanup_old_recordings(plogger: PipelineLogger) -> int:
    """30日以上前の録音ファイルを削除する。

    対象: ~/tools/radio_content_pipeline/data/recordings/*.m4a
    判定: ファイルの更新日時（mtime）が30日以上前

    Returns:
        削除したファイル数
    """
    recordings_dir = PIPELINE_DIR / "data" / "recordings"
    if not recordings_dir.exists():
        return 0

    cutoff = datetime.now(tz=JST) - timedelta(days=RECORDINGS_RETENTION_DAYS)
    deleted = 0

    for f in recordings_dir.glob("*.m4a"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=JST)
        if mtime < cutoff:
            f.unlink()
            plogger.info(f"     削除: {f.name} (mtime: {mtime.strftime('%Y-%m-%d')})")
            deleted += 1

    return deleted


# ─── recording_tasks.json 読み込み ───────────────────────────────

def _read_recording_tasks() -> list[dict]:
    """ホスト側の recording-tasks.json を読み込む。

    Returns:
        pendingステータスのタスクリスト
    """
    if not RECORDING_TASKS_FILE.exists():
        return []
    content = RECORDING_TASKS_FILE.read_text(encoding="utf-8")
    if not content.strip():
        return []
    tasks = json.loads(content)
    return [t for t in tasks if t.get("status") == "pending"]


# ─── ジョブファイル生成 ───────────────────────────────────────────

def _create_job_file(programs: list[dict]) -> Path:
    """番組検索結果からジョブファイルを生成する。

    各番組に対して recording → transcription → summarization → notification
    の4段階の子ジョブを生成する。

    Args:
        programs: recording-tasks.json から取得したpendingタスクのリスト

    Returns:
        生成されたジョブファイルのパス
    """
    JOB_DIR.mkdir(parents=True, exist_ok=True)

    parent_id = generate_id()
    today = datetime.now(tz=JST).strftime("%Y-%m-%d")
    today_compact = datetime.now(tz=JST).strftime("%Y%m%d")

    child_jobs: list[dict] = []
    for i, prog in enumerate(programs):
        program_name = prog.get("program_name", "unknown")
        station_id = prog.get("station_id", "unknown")

        # file_path から実際のファイル名ステムを取得
        # recording-tasks.json の file_path: "/data/recordings/TBS_番組名_20260519.m4a"
        file_path_str = prog.get("file_path", "")
        if file_path_str:
            base_filename = Path(file_path_str).stem
        else:
            # フォールバック: program_name + 日付で構築
            base_filename = f"{station_id}_{program_name}_{today_compact}"

        seq_base = i * 4

        child_jobs.append({
            "job_id": f"{parent_id}-{seq_base + 1:03d}",
            "job_name": "recording",
            "status": "pending",
            "args": {"program": program_name, "station": station_id},
            "started_at": None,
            "completed_at": None,
        })
        child_jobs.append({
            "job_id": f"{parent_id}-{seq_base + 2:03d}",
            "job_name": "transcription",
            "status": "pending",
            "args": {"file": f"{base_filename}.m4a"},
            "started_at": None,
            "completed_at": None,
        })
        child_jobs.append({
            "job_id": f"{parent_id}-{seq_base + 3:03d}",
            "job_name": "summarization",
            "status": "pending",
            "args": {"file": f"{base_filename}.json"},
            "started_at": None,
            "completed_at": None,
        })
        child_jobs.append({
            "job_id": f"{parent_id}-{seq_base + 4:03d}",
            "job_name": "notification",
            "status": "pending",
            "args": {"file": f"{base_filename}_summary.md"},
            "started_at": None,
            "completed_at": None,
        })

    parent_job = {
        "job_id": parent_id,
        "job_name": PIPELINE_NAME,
        "status": "running",
        "started_at": now_jst(),
        "completed_at": None,
        "child_jobs": child_jobs,
    }

    file_path = JOB_DIR / f"{today}_{PIPELINE_NAME}.json"
    file_path.write_text(
        json.dumps(parent_job, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return file_path


# ─── ジョブファイル更新 ──────────────────────────────────────────

def _update_recording_jobs(job_file: Path, status: str) -> None:
    """全recording子ジョブのステータスを一括更新する。"""
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)

    now = now_jst()
    for child in data.get("child_jobs", []):
        if child.get("job_name") == "recording":
            if status == "running":
                child["status"] = "running"
                child["started_at"] = now
            elif status == "completed":
                child["status"] = "completed"
                child["completed_at"] = now
            elif status == "failed":
                child["status"] = "failed"
                child["completed_at"] = now

    # 録音完了時: transcription を pending に（既にpendingだが明示的に）
    if status == "completed":
        for child in data.get("child_jobs", []):
            if child.get("job_name") == "transcription":
                child["status"] = "pending"

    job_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _update_parent_status(job_file: Path, status: str, error: str | None = None) -> None:
    """親ジョブのステータスを更新する。"""
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)

    data["status"] = status
    if status in ("completed", "failed"):
        data["completed_at"] = now_jst()
    if error:
        data["error"] = error

    job_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ─── JSON パース ─────────────────────────────────────────────────

def _parse_discovery_result(stdout: str) -> dict | None:
    """docker compose run の stdout から番組検索結果JSONをパースする。

    main.py --run-now は最後に json.dumps(result, ...) を print するが、
    その前にログ行が混在する可能性があるため、最後のJSON部分を抽出する。
    """
    lines = stdout.strip().splitlines()

    # 末尾からJSON開始行（{）を探して結合
    json_lines: list[str] = []
    brace_count = 0
    found_end = False

    for line in reversed(lines):
        stripped = line.strip()
        if not found_end:
            if stripped.endswith("}"):
                found_end = True
            else:
                continue

        json_lines.insert(0, line)
        brace_count += stripped.count("{") - stripped.count("}")

        if brace_count == 0 and found_end:
            break

    if json_lines:
        try:
            return json.loads("\n".join(json_lines))
        except json.JSONDecodeError:
            pass

    # フォールバック: 各行を個別にパース試行（1行JSONの場合）
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue

    return None


# ─── メイン処理 ──────────────────────────────────────────────────

def run_pipeline(
    dry_run: bool = False,
    use_job_file: bool = True,
    slack_channel: str = "",
    slack_thread_ts: str = "",
) -> None:
    """パイプラインを実行する。"""
    # 環境変数ロード
    load_env()

    # ログ初期化
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plogger = PipelineLogger(
        "radio_content_pipeline",
        log_dir=LOG_DIR,
        max_lines=1000,
        keep_lines=200,
        agent_max_lines=500,
        agent_keep_lines=100,
    )
    plogger.rotate_all()

    # スリープ防止
    caffeinate_pid = start_caffeinate()

    try:
        _execute_pipeline(
            plogger,
            dry_run=dry_run,
            use_job_file=use_job_file,
            slack_channel=slack_channel,
            slack_thread_ts=slack_thread_ts,
        )
    except Exception as e:
        plogger.error(f"パイプライン異常終了: {e}")
        notify_log = plogger.get_log_file("slack-notify")
        _notify_slack_text(
            f"❌ radio_content_pipeline 異常終了: {e}",
            notify_log,
            channel=slack_channel,
            thread=slack_thread_ts or "compact",
        )
        raise
    finally:
        stop_caffeinate(caffeinate_pid)


def _execute_pipeline(
    plogger: PipelineLogger,
    *,
    dry_run: bool,
    use_job_file: bool,
    slack_channel: str,
    slack_thread_ts: str,
) -> None:
    """パイプラインの実行本体。"""
    plogger.info("radio_content_pipeline 起動")
    notify_log = plogger.get_log_file("slack-notify")
    discovery_log = plogger.get_log_file("discovery")
    recorder_log = plogger.get_log_file("recorder")

    # ディスパッチャー経由: 開始通知
    if slack_channel and slack_thread_ts:
        _notify_slack_text(
            "🚀 radio_content_pipeline 開始",
            notify_log,
            channel=slack_channel,
            thread=slack_thread_ts,
        )

    # ─── Step 1: 番組検索 ────────────────────────────────────
    plogger.info("Step 1: 番組検索（docker compose run recorder main.py --run-now）")

    if dry_run:
        plogger.info("   [dry-run] docker compose run --rm recorder python3 src/main.py --run-now")
        plogger.info("   [dry-run] 番組検索をスキップ")
        pending_tasks = _read_recording_tasks()
        if pending_tasks:
            plogger.info(f"   [dry-run] 既存pendingタスク: {len(pending_tasks)}件")
            for t in pending_tasks:
                plogger.info(f"   [dry-run]   - {t.get('program_name')} ({t.get('station_id')})")
        else:
            plogger.info("   [dry-run] pendingタスクなし")
        plogger.info("   [dry-run] Step 2: 録音をスキップ")
        plogger.info("✅ radio_content_pipeline dry-run 完了")
        return

    ok, stdout = _docker_compose_run(
        "recorder",
        ["python3", "src/main.py", "--run-now"],
        discovery_log,
        timeout=120,
    )

    if not ok:
        plogger.error(f"Step 1 失敗: {stdout}")
        _notify_slack_text(
            f"❌ radio_content_pipeline Step 1（番組検索）失敗: {stdout}",
            notify_log, channel=slack_channel, thread=slack_thread_ts or "compact",
        )
        return

    # stdout から結果JSONをパース
    discovery_result = _parse_discovery_result(stdout)
    if discovery_result is None:
        plogger.error("Step 1: 番組検索結果のJSONパースに失敗")
        _notify_slack_text(
            "❌ radio_content_pipeline Step 1: JSONパース失敗",
            notify_log, channel=slack_channel, thread=slack_thread_ts or "compact",
        )
        return

    discovered = discovery_result.get("discovered", 0)
    added = discovery_result.get("added", 0)
    skipped = discovery_result.get("skipped", 0)
    plogger.info(f"   番組検索完了: {discovered}件発見, {added}件追加, {skipped}件スキップ")

    # recording-tasks.json からpendingタスクの詳細を取得
    pending_tasks = _read_recording_tasks()
    if not pending_tasks:
        plogger.info("   pendingタスクなし — 録音不要")
        plogger.info("✅ radio_content_pipeline 完了（録音対象なし）")
        return

    plogger.info(f"   録音対象: {len(pending_tasks)}件")
    for t in pending_tasks:
        plogger.info(f"     - {t.get('program_name')} ({t.get('station_id')})")

    # ─── ジョブファイル生成 ──────────────────────────────────
    job_file: Path | None = None
    if use_job_file:
        plogger.info("ジョブファイル生成...")
        job_file = _create_job_file(pending_tasks)
        plogger.info(f"   ジョブファイル: {job_file}")
        _update_recording_jobs(job_file, "running")

    # ─── Step 2: 録音 ────────────────────────────────────────
    plogger.info("Step 2: 録音（docker compose run recorder recorder.py --once）")

    ok, stdout = _docker_compose_run(
        "recorder",
        ["python3", "src/recorder.py", "--once"],
        recorder_log,
        timeout=21600,  # 6時間タイムアウト
    )

    if not ok:
        plogger.error(f"Step 2 失敗: {stdout}")
        if job_file:
            _update_recording_jobs(job_file, "failed")
            _update_parent_status(job_file, "failed", error=f"録音失敗: {stdout}")
        _notify_slack_text(
            f"❌ radio_content_pipeline Step 2（録音）失敗: {stdout}",
            notify_log, channel=slack_channel, thread=slack_thread_ts or "compact",
        )
        return

    # 録音完了: recording → completed, transcription → pending
    if job_file:
        _update_recording_jobs(job_file, "completed")
    plogger.info("   録音完了")

    # ─── Step 3: クリーンアップ ──────────────────────────────
    plogger.info("Step 3: data/recordings/ クリーンアップ（30日超過ファイル削除）")
    cleanup_count = _cleanup_old_recordings(plogger)
    if cleanup_count > 0:
        plogger.info(f"   {cleanup_count}件の古い録音ファイルを削除")

    # ─── 完了 ────────────────────────────────────────────────
    plogger.info(
        f"✅ radio_content_pipeline 完了"
        f"（{len(pending_tasks)}件録音完了、文字起こし以降はウォッチャーに委譲）"
    )

    # ディスパッチャー経由: 完了通知
    if slack_channel and slack_thread_ts:
        _notify_slack_text(
            f"✅ radio_content_pipeline 完了（{len(pending_tasks)}件録音完了）",
            notify_log, channel=slack_channel, thread=slack_thread_ts,
        )


# ─── エントリポイント ────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ラジオ録音パイプライン日次トリガー",
    )
    parser.add_argument("--dry-run", action="store_true", help="実行せずに計画を表示")
    parser.add_argument("--no-job-file", action="store_true", help="ジョブファイルを生成しない")
    parser.add_argument("--slack-channel", default="", help="Slack通知先チャンネルID")
    parser.add_argument("--slack-thread-ts", default="", help="Slack通知先スレッドTS")
    args = parser.parse_args()

    run_pipeline(
        dry_run=args.dry_run,
        use_job_file=not args.no_job_file,
        slack_channel=args.slack_channel,
        slack_thread_ts=args.slack_thread_ts,
    )


if __name__ == "__main__":
    main()
