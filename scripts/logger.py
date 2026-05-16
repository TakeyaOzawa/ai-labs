"""
logger: パイプライン共通ロガーモジュール

目的:
    パイプラインおよびユーティリティスクリプトのログ出力を統一する。
    Python標準loggingモジュールをベースに、既存の[timestamp] emoji message
    フォーマットを維持しつつ、ログレベル制御・ローテーション・将来の
    クラウド移行（CloudWatch等）に対応する拡張ポイントを提供する。

使い方:
    from logger import get_logger, setup_pipeline_logging

    # 単体スクリプト用
    logger = get_logger("my-script")
    logger.info("処理開始")
    logger.error("失敗しました")

    # パイプライン用（ファイル出力 + ローテーション付き）
    logger = setup_pipeline_logging("daily", log_dir=Path("~/logs/jobs/scout_daily"))
    logger.info("パイプライン起動")

出力: コンソール（stdout/stderr）+ オプショナルなファイル出力
依存: 標準ライブラリのみ
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

# ログレベルと絵文字のマッピング
_LEVEL_EMOJI: dict[int, str] = {
    logging.DEBUG: "🔍",
    logging.INFO: "📋",
    logging.WARNING: "⚠️ ",
    logging.ERROR: "❌",
    logging.CRITICAL: "🔴",
}

# デフォルトのローテーション設定
DEFAULT_MAX_LINES = 1000
DEFAULT_KEEP_LINES = 200


# ─── Formatter ───────────────────────────────────────────────────

class PipelineFormatter(logging.Formatter):
    """パイプライン用フォーマッタ。既存の [timestamp] emoji message 形式を再現する。

    出力例:
        [2026-05-16T10:30:00+09:00] 📋 パイプライン起動
        [2026-05-16T10:30:01+09:00] ⚠️  ジョブファイル生成失敗
        [2026-05-16T10:30:02+09:00] ❌ エージェント失敗
    """

    def __init__(self, include_name: bool = False) -> None:
        """初期化。

        Args:
            include_name: ロガー名をメッセージに含めるか（[name] 形式）
        """
        super().__init__()
        self._include_name = include_name

    def format(self, record: logging.LogRecord) -> str:
        """レコードをフォーマットする。"""
        timestamp = datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        emoji = _LEVEL_EMOJI.get(record.levelno, "📋")
        message = record.getMessage()

        # インデント付きメッセージ（"   "で始まる）はタイムスタンプ+絵文字を省略
        if message.startswith("   "):
            return f"[{timestamp}]{message}"

        if self._include_name:
            return f"[{timestamp}] {emoji} [{record.name}] {message}"
        return f"[{timestamp}] {emoji} {message}"


class JsonFormatter(logging.Formatter):
    """CloudWatch Logs等向けJSON構造化フォーマッタ。

    出力例:
        {"timestamp":"2026-05-16T10:30:00+09:00","level":"INFO","name":"daily","message":"起動"}
    """

    def format(self, record: logging.LogRecord) -> str:
        """レコードをJSON形式でフォーマットする。"""
        import json

        timestamp = datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        entry: dict[str, str | dict] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        # extra フィールドがあれば追加
        if hasattr(record, "pipeline"):
            entry["pipeline"] = record.pipeline  # type: ignore[attr-defined]
        if hasattr(record, "agent"):
            entry["agent"] = record.agent  # type: ignore[attr-defined]

        return json.dumps(entry, ensure_ascii=False)


# ─── Handler ─────────────────────────────────────────────────────

class RotatingLineHandler(logging.FileHandler):
    """行数ベースのログローテーションHandler。

    既存の rotate_log() と同等のロジック:
    ファイルが max_lines を超えたら末尾 keep_lines 行に切り詰める。
    """

    def __init__(
        self,
        filename: str | Path,
        max_lines: int = DEFAULT_MAX_LINES,
        keep_lines: int = DEFAULT_KEEP_LINES,
    ) -> None:
        self._path = Path(filename)
        self._max_lines = max_lines
        self._keep_lines = keep_lines
        self._path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(str(self._path), mode="a", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        """レコードを書き込み、必要に応じてローテーションする。"""
        super().emit(record)
        self._maybe_rotate()

    def _maybe_rotate(self) -> None:
        """行数チェックしてローテーションする（毎回ではなく100行ごとにチェック）。"""
        # パフォーマンスのため、毎回ではなくファイルサイズで簡易判定
        try:
            if self._path.stat().st_size < self._max_lines * 80:
                return
        except OSError:
            return

        try:
            lines = self._path.read_text(encoding="utf-8", errors="replace").splitlines()
            if len(lines) > self._max_lines:
                # ストリームを閉じてから書き換え
                self.close()
                self._path.write_text(
                    "\n".join(lines[-self._keep_lines:]) + "\n",
                    encoding="utf-8",
                )
                # ストリームを再オープン
                self.stream = self._open()
        except OSError:
            pass


# ─── ファクトリ関数 ──────────────────────────────────────────────

def _resolve_log_level() -> int:
    """環境変数 LOG_LEVEL からログレベルを解決する。"""
    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, None)
    if isinstance(level, int):
        return level
    return logging.INFO


def _resolve_formatter() -> logging.Formatter:
    """環境変数 LOG_FORMAT からフォーマッタを解決する。"""
    fmt = os.environ.get("LOG_FORMAT", "text").lower()
    if fmt == "json":
        return JsonFormatter()
    return PipelineFormatter()


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """名前付きロガーを取得する。コンソール出力のみ。

    Args:
        name: ロガー名（スクリプト名やエージェント名）
        level: ログレベル（省略時: LOG_LEVEL環境変数 or INFO）

    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(f"pipeline.{name}")

    # 既にハンドラが設定されていれば再設定しない
    if logger.handlers:
        return logger

    resolved_level = level if level is not None else _resolve_log_level()
    logger.setLevel(resolved_level)
    logger.propagate = False

    # コンソールハンドラ（stdout）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(resolved_level)
    console.setFormatter(_resolve_formatter())
    logger.addHandler(console)

    return logger


def setup_pipeline_logging(
    name: str,
    log_dir: Path,
    log_file: str = "pipeline.log",
    max_lines: int = DEFAULT_MAX_LINES,
    keep_lines: int = DEFAULT_KEEP_LINES,
    level: int | None = None,
) -> logging.Logger:
    """パイプライン用のロガーをセットアップする。

    コンソール出力 + ファイル出力（ローテーション付き）を設定する。

    Args:
        name: パイプライン名（"daily" / "weekly"）
        log_dir: ログ出力ディレクトリ
        log_file: ログファイル名（デフォルト: pipeline.log）
        max_lines: ローテーション閾値（行数）
        keep_lines: ローテーション後に保持する行数
        level: ログレベル（省略時: LOG_LEVEL環境変数 or INFO）

    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(f"pipeline.{name}")

    # 既にハンドラが設定されていれば再設定しない
    if logger.handlers:
        return logger

    resolved_level = level if level is not None else _resolve_log_level()
    logger.setLevel(resolved_level)
    logger.propagate = False

    formatter = _resolve_formatter()

    # コンソールハンドラ（stdout）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(resolved_level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ファイルハンドラ（ローテーション付き）
    log_dir.mkdir(parents=True, exist_ok=True)
    file_path = log_dir / log_file
    file_handler = RotatingLineHandler(
        file_path, max_lines=max_lines, keep_lines=keep_lines,
    )
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ─── 後方互換ユーティリティ ──────────────────────────────────────

def rotate_log(log_file: Path, max_lines: int, keep_lines: int = 200) -> None:
    """ログファイルが max_lines を超えていたら末尾 keep_lines 行に切り詰める。

    後方互換: _pipeline_common.py の既存 rotate_log() と同一シグネチャ。
    setup_pipeline_logging() を使用する場合は RotatingLineHandler が
    自動でローテーションするため、この関数の呼び出しは不要。
    """
    if not log_file.exists():
        return
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > max_lines:
            log_file.write_text(
                "\n".join(lines[-keep_lines:]) + "\n", encoding="utf-8",
            )
    except OSError:
        pass


def log_error(pipeline: str, agent: str, message: str) -> None:
    """構造化エラーログを出力する。

    後方互換: _pipeline_common.py の既存 log_error() と同一シグネチャ。
    常に stderr に出力する（launchd StandardErrorPath との互換性維持）。
    """
    timestamp = datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    print(f"[{timestamp}] [{pipeline}] > [{agent}] {message}", file=sys.stderr)
