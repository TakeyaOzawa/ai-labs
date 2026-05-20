#!/usr/bin/env python3.12
"""
transcriber: 文字起こしワーカー（サブプロセスB）

目的:
    タスクリストを監視し、faster-whisperで音声ファイルを文字起こしする。
    完了後にSlack通知とLLM要約を非同期で実行する。

使い方:
    python3.12 src/transcriber.py
    python3.12 src/transcriber.py --file /data/recordings/TBS_番組名_20260518.m4a
    python3.12 src/transcriber.py --once

出力: 文字起こし結果JSON（/data/transcripts/）
依存: faster-whisper
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_manager import (
    TRANSCRIPTION_TASKS_FILE,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    STATUS_FAILED,
    check_timeouts,
    get_pending_tasks,
    update_status,
)

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

TRANSCRIPTS_DIR = Path(os.environ.get("TRANSCRIPTS_DIR", "/data/transcripts"))
SUMMARIES_DIR = Path(os.environ.get("SUMMARIES_DIR", "/data/summaries"))
POLL_INTERVAL = int(os.environ.get("TRANSCRIBER_POLL_INTERVAL", "30"))
MAX_CONCURRENT = int(os.environ.get("TRANSCRIBER_MAX_CONCURRENT", "1"))
TIMEOUT_HOURS = float(os.environ.get("TRANSCRIBER_TIMEOUT_HOURS", "6"))

# Whisper設定
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
WHISPER_BEAM_SIZE = int(os.environ.get("WHISPER_BEAM_SIZE", "1"))
WHISPER_VAD_FILTER = os.environ.get("WHISPER_VAD_FILTER", "false").lower() == "true"
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "ja")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# グレースフルシャットダウン用フラグ
_shutdown_requested = False


def _signal_handler(signum, frame):
    """SIGTERMハンドラ: グレースフルシャットダウンを要求する。"""
    global _shutdown_requested
    _shutdown_requested = True
    print("[transcriber] Shutdown requested, finishing current task...")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ─── Whisperモデル管理 ───────────────────────────────────────────

_whisper_model = None


def get_whisper_model():
    """Whisperモデルをロード（シングルトン）。"""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print(
            f"[transcriber] Loading model: {WHISPER_MODEL} "
            f"(compute_type={WHISPER_COMPUTE_TYPE})"
        )
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("[transcriber] Model loaded")
    return _whisper_model


# ─── 文字起こし処理 ──────────────────────────────────────────────

def get_audio_duration(audio_path: Path) -> float:
    """ffprobeで音声ファイルの長さを取得する。

    Args:
        audio_path: 音声ファイルパス

    Returns:
        秒数

    Raises:
        ValueError: ファイルが不正な場合
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"Invalid audio file: {audio_path.name} — {result.stderr}"
        )
    return float(result.stdout.strip())


def transcribe_audio(
    audio_path: Path,
    initial_prompt: str | None = None,
) -> dict:
    """音声ファイルを文字起こしする。

    Args:
        audio_path: 音声ファイルパス
        initial_prompt: 固有名詞認識改善用のプロンプト

    Returns:
        文字起こし結果dict
    """
    audio_duration = get_audio_duration(audio_path)

    print(
        f"[transcriber] Processing: {audio_path.name} "
        f"(duration: {audio_duration:.0f}s)"
    )
    start_time = time.time()

    model = get_whisper_model()

    transcribe_kwargs = {
        "language": WHISPER_LANGUAGE,
        "beam_size": WHISPER_BEAM_SIZE,
        "vad_filter": WHISPER_VAD_FILTER,
    }
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt

    segments, info = model.transcribe(
        str(audio_path),
        **transcribe_kwargs,
    )

    transcript_segments = []
    full_text = ""
    for segment in segments:
        transcript_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
        })
        full_text += segment.text

    elapsed = time.time() - start_time
    rtf = elapsed / audio_duration if audio_duration > 0 else 0

    result = {
        "file": audio_path.name,
        "model": WHISPER_MODEL,
        "engine": "faster-whisper",
        "language": info.language,
        "language_probability": info.language_probability,
        "duration_seconds": audio_duration,
        "processing_seconds": elapsed,
        "realtime_factor": rtf,
        "beam_size": WHISPER_BEAM_SIZE,
        "vad_filter": WHISPER_VAD_FILTER,
        "initial_prompt": initial_prompt,
        "segments": transcript_segments,
        "full_text": full_text,
        "char_count": len(full_text),
    }

    print(
        f"[transcriber] Done: {elapsed:.1f}s "
        f"(RTF: {rtf:.2f}x, chars: {len(full_text)})"
    )

    return result


# ─── タスク処理 ──────────────────────────────────────────────────

def process_transcription_task(task: dict) -> dict:
    """1件の文字起こしタスクを処理する。

    Args:
        task: タスクエントリ

    Returns:
        処理結果dict
    """
    file_path = task["file_path"]
    program_name = task["program_name"]
    audio_path = Path(file_path)

    # ステータスをprocessingに更新
    update_status(TRANSCRIPTION_TASKS_FILE, file_path, STATUS_PROCESSING)

    try:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # initial_promptに番組名を含めて固有名詞認識を改善
        initial_prompt = program_name if program_name else None

        # 文字起こし実行
        result = transcribe_audio(audio_path, initial_prompt=initial_prompt)

        # JSON保存
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        transcript_path = TRANSCRIPTS_DIR / f"{audio_path.stem}.json"
        transcript_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ステータスをsuccessに更新
        update_status(TRANSCRIPTION_TASKS_FILE, file_path, STATUS_SUCCESS)

        # 非同期通知・要約（fire-and-forget）
        _notify_completion(task, result, transcript_path)
        _request_summary(task, result)

        return {
            "success": True,
            "file_path": file_path,
            "transcript_path": str(transcript_path),
            "program_name": program_name,
            "char_count": result["char_count"],
            "processing_seconds": result["processing_seconds"],
        }

    except Exception as e:
        error_msg = str(e)
        update_status(
            TRANSCRIPTION_TASKS_FILE, file_path, STATUS_FAILED, error=error_msg
        )
        print(
            f"[transcriber] Failed: {program_name} — {error_msg}",
            file=sys.stderr,
        )
        return {
            "success": False,
            "file_path": file_path,
            "program_name": program_name,
            "error": error_msg,
        }


def _notify_completion(task: dict, result: dict, transcript_path: Path):
    """文字起こし完了をSlack通知する（非同期、失敗しても無視）。"""
    try:
        from notifier import notify_transcription_complete
        notify_transcription_complete(
            program_name=task["program_name"],
            file_path=str(transcript_path),
            char_count=result["char_count"],
            processing_seconds=result["processing_seconds"],
            duration_seconds=result["duration_seconds"],
        )
    except Exception as e:
        print(f"[transcriber] Notification failed: {e}", file=sys.stderr)


def _request_summary(task: dict, result: dict):
    """LLM要約を非同期で依頼する（失敗しても無視）。"""
    try:
        from summarizer import summarize_async
        summarize_async(
            program_name=task["program_name"],
            full_text=result["full_text"],
            audio_filename=result["file"],
        )
    except Exception as e:
        print(f"[transcriber] Summary request failed: {e}", file=sys.stderr)


# ─── ワーカーループ ──────────────────────────────────────────────

def run_worker_loop():
    """タスクリストを監視し、文字起こしを順次実行するメインループ。"""
    print(f"[transcriber] Worker started (max_concurrent={MAX_CONCURRENT})")
    print(f"[transcriber] Poll interval: {POLL_INTERVAL}s")
    print(f"[transcriber] Model: {WHISPER_MODEL}, beam_size={WHISPER_BEAM_SIZE}")
    print(f"[transcriber] Output dir: {TRANSCRIPTS_DIR}")

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    while not _shutdown_requested:
        # タイムアウトチェック
        timed_out = check_timeouts(TRANSCRIPTION_TASKS_FILE, TIMEOUT_HOURS)
        if timed_out:
            print(
                f"[transcriber] {len(timed_out)} task(s) timed out, "
                f"reset to pending"
            )

        # pendingタスクを1件取得（CPU負荷が高いため1件ずつ）
        pending = get_pending_tasks(
            TRANSCRIPTION_TASKS_FILE, limit=MAX_CONCURRENT
        )
        if not pending:
            time.sleep(POLL_INTERVAL)
            continue

        # 1件ずつ順次処理
        for task in pending:
            if _shutdown_requested:
                break
            process_transcription_task(task)

        if not _shutdown_requested:
            time.sleep(POLL_INTERVAL)

    print("[transcriber] Worker stopped")


# ─── 手動実行モード ──────────────────────────────────────────────

def manual_transcribe(file_path: str) -> None:
    """手動で特定ファイルを文字起こしする。"""
    audio_path = Path(file_path)
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[transcriber] Manual transcription: {audio_path.name}")

    # ファイル名から番組名を推定
    parts = audio_path.stem.split("_")
    program_name = "_".join(parts[1:-1]) if len(parts) >= 3 else audio_path.stem

    result = transcribe_audio(audio_path, initial_prompt=program_name)

    # JSON保存
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = TRANSCRIPTS_DIR / f"{audio_path.stem}.json"
    transcript_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    output = {
        "success": True,
        "transcript_path": str(transcript_path),
        "char_count": result["char_count"],
        "processing_seconds": result["processing_seconds"],
        "realtime_factor": result["realtime_factor"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="文字起こしワーカー — faster-whisper"
    )
    parser.add_argument(
        "--file",
        help="手動文字起こし: 音声ファイルパス",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="1回だけpendingタスクを処理して終了",
    )
    args = parser.parse_args()

    if args.file:
        manual_transcribe(args.file)
    elif args.once:
        all_results = []
        while True:
            pending = get_pending_tasks(TRANSCRIPTION_TASKS_FILE, limit=9999)
            if not pending:
                break
            print(
                f"[transcriber] Processing {len(pending)} pending task(s)...",
                file=sys.stderr,
            )
            for task in pending:
                result = process_transcription_task(task)
                all_results.append(result)

        if not all_results:
            print("[transcriber] No pending tasks", file=sys.stderr)
            summary = {
                "mode": "once",
                "total": 0,
                "success": 0,
                "failed": 0,
                "results": [],
            }
            print(json.dumps(summary, ensure_ascii=False))
            return

        success_count = sum(1 for r in all_results if r["success"])
        failed_count = len(all_results) - success_count
        summary = {
            "mode": "once",
            "total": len(all_results),
            "success": success_count,
            "failed": failed_count,
            "results": all_results,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if failed_count > 0:
            sys.exit(1)
    else:
        run_worker_loop()


if __name__ == "__main__":
    main()
