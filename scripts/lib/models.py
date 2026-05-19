"""models: ドメインモデル（Step, Executor, StepParams等）。

外部依存ゼロ。テストで軽量にimport可能。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ═══════════════════════════════════════════════════════════════════
# データモデル: Step / Executor / StepParams
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RetryPolicy:
    """リトライポリシー。"""

    max_attempts: int = 1  # 最大試行回数（1=リトライなし）
    delay: int = 30  # リトライ間隔（秒）
    backoff: str = "fixed"  # "fixed" | "exponential"


# ─── Executor 種別 ───────────────────────────────────────────────


@dataclass
class Executor:
    """実行方式の基底。"""

    type: str = ""


@dataclass
class AgentExecutor(Executor):
    """AI CLIエージェント実行。"""

    type: str = field(default="agent", init=False)
    agent_name: str = ""
    prompt_text: str = ""


@dataclass
class ScriptExecutor(Executor):
    """Python/シェルスクリプト実行。"""

    type: str = field(default="script", init=False)
    command: str = ""
    env: dict[str, str] | None = None


@dataclass
class CompositeExecutor(Executor):
    """子ステップを順次実行する複合ステップ。"""

    type: str = field(default="composite", init=False)


# ─── StepParams ──────────────────────────────────────────────────


@dataclass
class InputParams:
    """入力パラメータ。"""

    source_type: str = "none"  # "file" | "theme" | "url" | "none"
    source_path: str = ""
    source_theme: str = ""
    source_url: str = ""
    format_ref: str = ""


@dataclass
class OutputParams:
    """出力パラメータ。"""

    enabled: bool = True
    path: str = ""
    format_ref: str = ""


@dataclass
class LogParams:
    """ログパラメータ。"""

    enabled: bool = True
    path: str = ""
    level: str = "info"  # "debug" | "info" | "error"


@dataclass
class SlackParams:
    """Slack通知パラメータ。"""

    enabled: bool = True
    channel: str = ""  # 空=デフォルト（SLACK_DISPATCH_DM_CHANNEL）
    thread_mode: str = "compact"  # "compact" | "sequential"
    thread_ts: str = ""  # 既存スレッドへ返信時
    source: str = "output"  # "output" | "text"
    source_text: str = ""
    token_env: str = "MY_SLACK_OAUTH_TOKEN"
    level: str = "info"  # "debug" | "info" | "error"


@dataclass
class JobParams:
    """ジョブ管理パラメータ。"""

    enabled: bool = False
    file: str = ""
    id: str = ""
    level: str = "info"  # "debug" | "info" | "error"


@dataclass
class StepParams:
    """全executor共通のパラメータ。"""

    input: InputParams | None = None
    output: OutputParams | None = None
    log: LogParams | None = None
    slack: SlackParams | None = None
    job: JobParams | None = None


# ─── Step ────────────────────────────────────────────────────────


@dataclass
class Step:
    """パイプラインの1実行単位（再帰的にネスト可能）。"""

    name: str
    executor: Executor

    # 実行制御
    mode: str = "sync"  # "sync" | "async"
    timeout: int = 300  # タイムアウト秒（0=無制限）
    retry: RetryPolicy | None = None
    depends_on: list[str] | None = None

    # 入出力パラメータ
    params: StepParams | None = None

    # ネスト（サブパイプライン相当）
    steps: list[Step] | None = None


# ─── PipelineConfig / PipelineContext ────────────────────────────


@dataclass
class PipelineContext:
    """run_pipeline() が構築し build_steps に渡すランタイム情報。"""

    base_date: str
    log_dir: Path
    use_job_file: bool
    slack_channel: str = ""
    slack_thread_ts: str = ""


@dataclass
class PipelineConfig:
    """各パイプラインが定義する設定（最小化）。"""

    name: str
    build_steps: Callable[[str, PipelineContext], list[Step]]
    default_base_date: Callable[[], str]


# ─── ExecutionContext ────────────────────────────────────────────


@dataclass
class ExecutionContext:
    """ステップ実行時の共有コンテキスト。"""

    job_file: Path | None
    use_job_file: bool
    base_date: str
    plogger: object  # PipelineLogger（循環import回避のためobject型）
    completed_names: set[str] = field(default_factory=set)
    slack_channel: str = ""
    slack_thread_ts: str = ""
