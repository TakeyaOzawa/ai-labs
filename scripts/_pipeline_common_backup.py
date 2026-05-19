"""
_pipeline_common: パイプラインスクリプト共通モジュール（統一ステップモデル）

宣言的な Step / Executor / StepParams による統一パイプライン実行基盤。
各パイプラインスクリプトは build_steps() で Step ツリーを定義し、
run_pipeline() が再帰的に実行する。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from logger import (
    PipelineLogger,
    log_error,
    rotate_log,
    setup_pipeline_logging,
)

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
MAX_LOG_LINES = 1000
MAX_AGENT_LOG_LINES = 500


# ═══════════════════════════════════════════════════════════════════
# データモデル: Step / Executor / StepParams
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RetryPolicy:
    """リトライポリシー。"""
    max_attempts: int = 1       # 最大試行回数（1=リトライなし）
    delay: int = 30             # リトライ間隔（秒）
    backoff: str = "fixed"      # "fixed" | "exponential"


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
    source_type: str = "none"       # "file" | "theme" | "url" | "none"
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
    level: str = "info"             # "debug" | "info" | "error"


@dataclass
class SlackParams:
    """Slack通知パラメータ。"""
    enabled: bool = True
    channel: str = ""               # 空=デフォルト（SLACK_DISPATCH_DM_CHANNEL）
    thread_mode: str = "compact"    # "compact" | "sequential"
    thread_ts: str = ""             # 既存スレッドへ返信時
    source: str = "output"          # "output" | "text"
    source_text: str = ""
    token_env: str = "MY_SLACK_OAUTH_TOKEN"
    level: str = "info"             # "debug" | "info" | "error"


@dataclass
class JobParams:
    """ジョブ管理パラメータ。"""
    enabled: bool = False
    file: str = ""
    id: str = ""
    level: str = "info"             # "debug" | "info" | "error"


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
    mode: str = "sync"              # "sync" | "async"
    timeout: int = 300              # タイムアウト秒（0=無制限）
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


# ═══════════════════════════════════════════════════════════════════
# ユーティリティ関数
# ═══════════════════════════════════════════════════════════════════

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


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


def generate_id() -> str:
    """ジョブID用のユニークIDを生成する。"""
    return uuid.uuid4().hex[:12]


# ─── AI コマンド実行 ─────────────────────────────────────────────

def _load_ai_command_builder():
    """ai-cli-utils.py モジュールを遅延ロードする。"""
    from importlib.util import module_from_spec, spec_from_file_location
    builder_path = SCRIPTS_DIR / "ai-cli-utils.py"
    spec = spec_from_file_location("ai_cli_utils", builder_path)
    mod = module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_ai_command_builder = None


def _get_ai_builder():
    """AI コマンドビルダーを取得（キャッシュ付き）。"""
    global _ai_command_builder
    if _ai_command_builder is None:
        _ai_command_builder = _load_ai_command_builder()
    return _ai_command_builder


def build_agent_prompt_with_params(step: Step) -> str:
    """Step の params から agent_params YAMLブロックを生成し、prompt_text に結合する。"""
    executor = step.executor
    if not isinstance(executor, AgentExecutor):
        return ""

    prompt = executor.prompt_text
    params = step.params

    # agent_params ブロック生成（input/output のみエージェントに渡す）
    if params and (params.input or params.output):
        yaml_lines = ["---", "agent_params:"]

        if params.input:
            inp = params.input
            yaml_lines.append("  input:")
            yaml_lines.append(f"    source_type: {inp.source_type}")
            if inp.source_path:
                yaml_lines.append(f'    source_path: "{inp.source_path}"')
            if inp.source_theme:
                yaml_lines.append(f'    source_theme: "{inp.source_theme}"')
            if inp.source_url:
                yaml_lines.append(f'    source_url: "{inp.source_url}"')
            if inp.format_ref:
                yaml_lines.append(f'    format_ref: "{inp.format_ref}"')

        if params.output:
            out = params.output
            yaml_lines.append("  output:")
            yaml_lines.append(f"    enabled: {str(out.enabled).lower()}")
            if out.path:
                yaml_lines.append(f'    path: "{out.path}"')
            if out.format_ref:
                yaml_lines.append(f'    format_ref: "{out.format_ref}"')

        yaml_lines.append("---")
        yaml_block = "\n".join(yaml_lines)
        prompt = f"{yaml_block}\n{prompt}"

    return prompt


def run_ai_command(prompt: str, log_file: Path, agent_name: str = "",
                   timeout: int = 0) -> tuple[bool, str]:
    """AIコマンドを実行し、(成功フラグ, 詳細理由) を返す。

    Returns:
        (True, ""): 成功
        (False, reason): 失敗（理由付き）
    """
    builder = _get_ai_builder()
    cmd = builder.build_ai_command(prompt, agent_name=agent_name)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd, stdout=f, stderr=subprocess.STDOUT,
                timeout=timeout if timeout > 0 else None,
                cwd=str(HOME),
            )
        if result.returncode == 0:
            return True, ""
        ai_type = os.environ.get("AI_COMMAND_TYPE", "claude")
        return False, f"{ai_type} exit non-zero"
    except subprocess.TimeoutExpired:
        return False, f"timeout ({timeout}s)"


# ─── Slack通知 ───────────────────────────────────────────────────

def run_slack_notify_async(
    file_path: Path,
    log_file: Path,
    channel: str = "",
    thread: str = "",
) -> int:
    """notify-slack.pyを新規プロセスで非同期に実行する（fire-and-forget）。"""
    cmd = [
        "python3.12",
        str(SCRIPTS_DIR / "notify-slack.py"),
        "--file", str(file_path),
    ]
    if channel:
        cmd.extend(["--channel", channel])
    if thread:
        cmd.extend(["--thread", thread])
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            proc = subprocess.Popen(
                cmd, stdout=f, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return proc.pid
    except OSError:
        return 0


def run_slack_notify(
    file_path: Path,
    log_file: Path,
    channel: str = "",
    thread: str = "",
) -> bool:
    """notify-slack.pyを同期実行する。"""
    cmd = [
        "python3.12",
        str(SCRIPTS_DIR / "notify-slack.py"),
        "--file", str(file_path),
    ]
    if channel:
        cmd.extend(["--channel", channel])
    if thread:
        cmd.extend(["--thread", thread])
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return result.returncode == 0


def _notify_slack_reply(
    text: str, channel: str, thread_ts: str, log_file: Path,
) -> None:
    """Slackスレッドにテキスト返信する（同期）。"""
    notify_script = SCRIPTS_DIR / "notify-slack.py"
    if not notify_script.exists():
        return
    cmd = [
        "python3.12", str(notify_script),
        "--text", text,
        "--channel", channel,
        "--thread", thread_ts,
    ]
    with open(log_file, "a", encoding="utf-8") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)


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


# ═══════════════════════════════════════════════════════════════════
# ジョブファイル自動生成
# ═══════════════════════════════════════════════════════════════════

def generate_job_file(
    pipeline_name: str, base_date: str, steps: list[Step],
) -> Path:
    """Step ツリーからジョブファイルを自動生成する。"""
    job_dir = HOME / "Documents" / "works" / "jobs"
    job_dir.mkdir(parents=True, exist_ok=True)

    parent_id = generate_id()
    parent_job = {
        "job_id": parent_id,
        "job_name": pipeline_name,
        "base_date": base_date,
        "status": "running",
        "started_at": now_jst(),
        "timeout": sum(s.timeout for s in steps),
        "child_jobs": [_step_to_job(s) for s in steps],
    }

    file_path = job_dir / f"{base_date}_{pipeline_name}.json"
    file_path.write_text(
        json.dumps(parent_job, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return file_path


def _step_to_job(step: Step) -> dict:
    """Step → ジョブ定義の変換（再帰的）。"""
    job: dict = {
        "job_id": generate_id(),
        "job_name": step.name,
        "status": "pending",
        "timeout": step.timeout,
    }
    if step.retry:
        job["retry_delay"] = step.retry.delay
        job["max_attempts"] = step.retry.max_attempts
    if step.depends_on:
        job["depends_on"] = step.depends_on
    if step.steps:
        job["child_jobs"] = [_step_to_job(s) for s in step.steps]
    return job


# ─── ジョブ更新 ──────────────────────────────────────────────────

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


def get_child_job_id(job_file: Path, job_name: str) -> str:
    """ジョブファイルから指定ジョブ名のIDを再帰検索で取得する。"""
    with open(job_file, encoding="utf-8") as f:
        data = json.load(f)
    return _find_job_id_by_name(data.get("child_jobs", []), job_name)


def _find_job_id_by_name(jobs: list[dict], job_name: str) -> str:
    """ジョブツリーを再帰的に探索し、指定名のジョブIDを返す。"""
    for job in jobs:
        if job.get("job_name") == job_name:
            return job.get("job_id", "")
        found = _find_job_id_by_name(job.get("child_jobs", []), job_name)
        if found:
            return found
    return ""


# ═══════════════════════════════════════════════════════════════════
# ステップ実行エンジン
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExecutionContext:
    """ステップ実行時の共有コンテキスト。"""
    job_file: Path | None
    use_job_file: bool
    base_date: str
    plogger: PipelineLogger
    completed_names: set[str] = field(default_factory=set)
    slack_channel: str = ""
    slack_thread_ts: str = ""



def execute_steps(
    steps: list[Step], context: ExecutionContext,
) -> tuple[int, int, int]:
    """ステップリストを順次実行する（再帰対応）。

    Returns:
        (success_count, failed_count, skipped_count)
    """
    success = 0
    failed = 0
    skipped = 0

    for step in steps:
        # 依存チェック
        if step.depends_on:
            unmet = [d for d in step.depends_on if d not in context.completed_names]
            if unmet:
                context.plogger.info(
                    f"⏭️  {step.name} スキップ"
                    f"（未完了の依存先: {', '.join(unmet)}）"
                )
                skipped += 1
                continue

        context.plogger.info(f"🔄 {step.name} 実行中...")

        # ジョブステータス更新: running
        child_job_id = ""
        if context.use_job_file and context.job_file:
            child_job_id = get_child_job_id(context.job_file, step.name)
            if child_job_id:
                update_job(context.job_file, job_id=child_job_id,
                           updates={"status": "running", "started_at": now_jst()})
                update_job(context.job_file, scope="parent",
                           updates={"status_detail": f"{step.name} 実行中"})

        # 実行（リトライ対応）
        max_attempts = step.retry.max_attempts if step.retry else 1
        delay = step.retry.delay if step.retry else 30
        ok = False
        reason = ""

        for attempt in range(max_attempts):
            if attempt > 0:
                context.plogger.info(
                    f"   🔁 {step.name} リトライ ({attempt + 1}/{max_attempts})..."
                )
                time.sleep(delay)
                if step.retry and step.retry.backoff == "exponential":
                    delay *= 2

            ok, reason = _execute_step(step, context)
            if ok:
                break

        # 結果処理
        if ok:
            context.plogger.info(f"   ✅ {step.name} 完了")
            success += 1
            context.completed_names.add(step.name)
            if context.use_job_file and context.job_file and child_job_id:
                update_job(context.job_file, job_id=child_job_id, updates={
                    "status": "completed", "completed_at": now_jst(),
                })
            # Slack通知（非同期）
            _notify_step_completion(step, context)
        else:
            context.plogger.error(f"   {step.name} 失敗: {reason}")
            context.plogger.log_error(step.name, reason)
            failed += 1
            if context.use_job_file and context.job_file and child_job_id:
                update_job(context.job_file, job_id=child_job_id, updates={
                    "status": "failed", "completed_at": now_jst(),
                    "error": reason,
                })

    return success, failed, skipped


def _execute_step(
    step: Step, context: ExecutionContext,
) -> tuple[bool, str]:
    """単一ステップを実行する。Returns: (success, reason)。"""
    executor = step.executor

    if isinstance(executor, CompositeExecutor):
        # 子ステップを再帰実行
        if not step.steps:
            return True, ""
        child_context = ExecutionContext(
            job_file=context.job_file,
            use_job_file=context.use_job_file,
            base_date=context.base_date,
            plogger=context.plogger,
            completed_names=set(),
            slack_channel=context.slack_channel,
            slack_thread_ts=context.slack_thread_ts,
        )
        s, f, _ = execute_steps(step.steps, child_context)
        if f > 0:
            return False, f"{f} sub-steps failed"
        return True, ""

    if isinstance(executor, ScriptExecutor):
        return _execute_script(executor, step, context)

    if isinstance(executor, AgentExecutor):
        return _execute_agent(executor, step, context)

    return False, f"unknown executor type: {executor.type}"


def _execute_script(
    executor: ScriptExecutor, step: Step, context: ExecutionContext,
) -> tuple[bool, str]:
    """ScriptExecutor を実行する。"""
    log_file = context.plogger.get_agent_log(step.name)
    env = os.environ.copy()
    if executor.env:
        env.update(executor.env)

    cmd_parts = executor.command.split()
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            result = subprocess.run(
                cmd_parts, stdout=f, stderr=subprocess.STDOUT,
                env=env,
                timeout=step.timeout if step.timeout > 0 else None,
            )
        if result.returncode == 0:
            return True, ""
        return False, f"script exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timeout ({step.timeout}s)"
    except OSError as e:
        return False, f"OSError: {e}"


def _execute_agent(
    executor: AgentExecutor, step: Step, context: ExecutionContext,
) -> tuple[bool, str]:
    """AgentExecutor を実行する。"""
    log_file = context.plogger.get_agent_log(step.name)
    prompt = build_agent_prompt_with_params(step)
    return run_ai_command(
        prompt, log_file, agent_name=executor.agent_name,
        timeout=step.timeout,
    )


def _notify_step_completion(step: Step, context: ExecutionContext) -> None:
    """ステップ完了後のSlack通知を実行する。"""
    params = step.params
    if not params or not params.slack or not params.slack.enabled:
        return
    if not params.output or not params.output.path:
        return

    slack = params.slack
    output_path = Path(params.output.path)
    if not output_path.is_absolute():
        output_path = HOME / output_path

    if not output_path.exists():
        return

    notify_log = context.plogger.get_notify_log()

    # thread 引数の決定
    thread = ""
    if slack.thread_ts:
        thread = slack.thread_ts
    elif context.slack_thread_ts:
        thread = context.slack_thread_ts
    elif slack.thread_mode == "compact":
        thread = "compact"

    channel = slack.channel or context.slack_channel or ""

    run_slack_notify_async(output_path, notify_log, channel=channel, thread=thread)


# ═══════════════════════════════════════════════════════════════════
# run_pipeline: メインエントリポイント
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(config: PipelineConfig) -> None:
    """パイプラインの共通実行フロー。"""

    # ─── オプション解析 ───────────────────────────────────────
    use_job_file = True
    slack_channel: str = ""
    slack_thread_ts: str = ""
    positional_args: list[str] = []

    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--no-job-file":
            use_job_file = False
        elif arg == "--slack-channel" and i + 1 < len(argv):
            i += 1
            slack_channel = argv[i]
        elif arg == "--slack-thread-ts" and i + 1 < len(argv):
            i += 1
            slack_thread_ts = argv[i]
        else:
            positional_args.append(arg)
        i += 1

    # 基準日
    base_date = positional_args[0] if positional_args else config.default_base_date()

    # ─── ログ初期化 ──────────────────────────────────────────
    log_dir = HOME / "logs" / "jobs" / config.name
    log_dir.mkdir(parents=True, exist_ok=True)
    plogger = PipelineLogger(
        config.name, log_dir=log_dir,
        max_lines=MAX_LOG_LINES, keep_lines=200,
        agent_max_lines=MAX_AGENT_LOG_LINES, agent_keep_lines=100,
    )
    plogger.rotate_all()

    # ─── 環境準備 ────────────────────────────────────────────
    caffeinate_pid = start_caffeinate()
    load_env()

    # 収集フェーズ用の環境変数設定
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("SLACK_REFERENCE_BOT_TOKEN", "")
    os.environ["SLACK_TEAM_ID"] = os.environ.get("SLACK_REFERENCE_TEAM_ID", "")

    label = config.name
    notify_log = plogger.get_notify_log()
    plogger.info(f"{label}パイプライン起動（基準日: {base_date}）")

    # ディスパッチャー経由: 開始通知
    if slack_channel and slack_thread_ts:
        _notify_slack_reply(
            f"🚀 {label}パイプライン開始（基準日: {base_date}）",
            slack_channel, slack_thread_ts, notify_log,
        )

    # ─── ステップツリー生成 ───────────────────────────────────
    pipeline_context = PipelineContext(
        base_date=base_date,
        log_dir=log_dir,
        use_job_file=use_job_file,
        slack_channel=slack_channel,
        slack_thread_ts=slack_thread_ts,
    )
    steps = config.build_steps(base_date, pipeline_context)

    # ─── ジョブファイル自動生成 ───────────────────────────────
    job_file: Path | None = None
    if use_job_file:
        plogger.info("ジョブファイル生成...")
        job_file = generate_job_file(config.name, base_date, steps)
        plogger.info(f"   ジョブファイル: {job_file}")

    # ─── ステップ実行 ────────────────────────────────────────
    plogger.info("ステップ実行開始...")
    exec_context = ExecutionContext(
        job_file=job_file,
        use_job_file=use_job_file,
        base_date=base_date,
        plogger=plogger,
        slack_channel=slack_channel,
        slack_thread_ts=slack_thread_ts,
    )
    success, failed_count, skipped_count = execute_steps(steps, exec_context)

    # ─── 親ジョブ完了処理 ────────────────────────────────────
    total = success + failed_count + skipped_count
    if use_job_file and job_file:
        if failed_count > 0:
            update_job(job_file, scope="parent", updates={
                "status": "failed", "completed_at": now_jst(),
                "error": f"{failed_count}/{total} steps failed",
            })
        else:
            update_job(job_file, scope="parent", updates={
                "status": "completed", "completed_at": now_jst(),
                "status_detail": "全ステップ完了",
            })

    # ─── 完了サマリー ────────────────────────────────────────
    plogger.info(
        f"📊 実行完了: ✅{success}件 / ❌{failed_count}件 / ⏭️{skipped_count}件スキップ"
        f" (全{total}件)"
    )
    if use_job_file and job_file:
        plogger.info(f"   ジョブファイル: {job_file}")
    plogger.info(f"✅ {label}パイプライン完了（基準日: {base_date}）")

    # ディスパッチャー経由: 完了通知
    if slack_channel and slack_thread_ts:
        summary = f"✅ {label}パイプライン完了（基準日: {base_date}）\n"
        summary += f"✅{success}件 / ❌{failed_count}件 / ⏭️{skipped_count}件スキップ"
        _notify_slack_reply(summary, slack_channel, slack_thread_ts, notify_log)

    # スリープ防止解除
    stop_caffeinate(caffeinate_pid)
