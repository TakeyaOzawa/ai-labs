"""
_pipeline_common: パイプラインスクリプト共通モジュール

日次・週次パイプラインで共有するユーティリティ関数群と
共通実行フロー（run_pipeline）を提供する。
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
MAX_LOG_LINES = 1000
MAX_AGENT_LOG_LINES = 500


# ─── パイプライン設定 ────────────────────────────────────────────

def _default_build_prompt(agent: str, base_date: str) -> str:
    """デフォルトのプロンプト構築。"""
    return (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
    )


@dataclass
class PipelineConfig:
    """各パイプラインが定義する設定。"""

    name: str                                # "daily" | "weekly"
    log_dir: Path                            # ログ出力ディレクトリ
    agents: list[str]                        # エージェントリスト
    notify_file_map: dict[str, str]          # エージェント名 → 通知ファイルテンプレート
    create_jobs_script: str                  # ジョブファイル生成スクリプト名
    default_base_date: Callable[[], str]     # 基準日デフォルト計算

    # RSS取得フック: 各パイプラインがRSS取得ステップ全体を定義
    rss_fetch_hook: Callable[[str, Path], None] | None = None

    # プロンプト構築: (agent, base_date) -> prompt
    build_prompt: Callable[[str, str], str] = field(default=_default_build_prompt)

    # 通知ファイルパス解決: (agent, base_date) -> Path | None
    # Noneを返すとNOTIFY_FILE_MAPのテンプレートを使用、Pathを返すとそれを使用
    resolve_notify_path: Callable[[str, str], Path | None] | None = None

    # エージェント実行前フック: (agent, base_date) -> skip_reason | None
    # 文字列を返すとスキップ（理由表示）、Noneを返すと通常実行
    pre_agent_hook: Callable[[str, str], str | None] | None = None

    # 全エージェント実行後の追加ステップ
    post_agents_hook: Callable[[str], None] | None = None

    # 通知後の追加ステップ
    post_notify_hook: Callable[[str], None] | None = None


# ─── ユーティリティ関数 ──────────────────────────────────────────

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


def run_kiro_cli(prompt: str, log_file: Path, agent_name: str = "") -> bool:
    """kiro-cliを実行し、成功/失敗を返す。"""
    cmd = ["kiro-cli", "chat", "--trust-all-tools", "--no-interactive"]
    if agent_name:
        cmd.extend(["--agent", agent_name])
    cmd.append(prompt)
    with open(log_file, "a", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return result.returncode == 0


def log_error(pipeline: str, agent: str, message: str) -> None:
    """error.logに親タスク > 子タスクの2階層ヘッダー付きでエラーを記録する。"""
    timestamp = now_jst()
    print(f"[{timestamp}] [{pipeline}] > [{agent}] {message}", file=sys.stderr)


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


# ─── 内部ヘルパー ────────────────────────────────────────────────

def _create_job_file(config: PipelineConfig, base_date: str) -> Path | None:
    """ジョブファイルを生成し、パスを返す。"""
    result = subprocess.run(
        ["python3.12", str(SCRIPTS_DIR / config.create_jobs_script), base_date],
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


# ─── 共通runner関数 ──────────────────────────────────────────────

def run_pipeline(config: PipelineConfig) -> None:
    """パイプラインの共通実行フロー。"""

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
        base_date = config.default_base_date()

    config.log_dir.mkdir(parents=True, exist_ok=True)

    # スリープ防止
    caffeinate_pid = start_caffeinate()

    # 環境変数ロード
    load_env()

    # 収集フェーズ用の環境変数設定
    os.environ["SLACK_BOT_TOKEN"] = os.environ.get("SLACK_REFERENCE_BOT_TOKEN", "")
    os.environ["SLACK_TEAM_ID"] = os.environ.get("SLACK_REFERENCE_TEAM_ID", "")

    # ログローテーション
    log_file = config.log_dir / "pipeline.log"
    rotate_log(log_file, MAX_LOG_LINES)

    # error.log ローテーション（launchd StandardErrorPath）
    error_log = config.log_dir / "pipeline-error.log"
    rotate_log(error_log, MAX_LOG_LINES)

    label = "日次" if config.name == "daily" else "週次"
    print(f"[{now_jst()}] 📋 {label}scoutパイプライン起動（基準日: {base_date}）")

    # ─── Step 0: ジョブファイル生成 ───────────────────────────────
    job_file: Path | None = None
    if use_job_file:
        print(f"[{now_jst()}] Step 0: ジョブファイル生成...")
        job_file = _create_job_file(config, base_date)
        if job_file:
            print(f"[{now_jst()}]    ジョブファイル: {job_file}")
            update_job(job_file, scope="parent",
                       updates={"status": "running", "started_at": now_jst()})
        else:
            print(f"[{now_jst()}] ⚠️  ジョブファイル生成失敗。進捗管理なしで続行。")
            use_job_file = False

    # ─── Step 1: RSSフィード事前取得 ─────────────────────────────
    print(f"[{now_jst()}] Step 1: RSSフィード事前取得...")
    if config.rss_fetch_hook:
        config.rss_fetch_hook(base_date, SCRIPTS_DIR)
    else:
        print("   ⏭️  RSSフック未定義（スキップ）")

    # ─── Step 2: エージェント実行ループ ──────────────────────────
    print(f"[{now_jst()}] Step 2: scoutエージェント実行開始...")

    success = 0
    failed = 0
    failed_names: list[str] = []

    for agent in config.agents:
        agent_start = now_jst()
        print(f"[{agent_start}] 🔄 {agent} 実行中...")

        agent_log = config.log_dir / f"{agent}.log"
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

        # pre_agent_hook でスキップ判定
        if config.pre_agent_hook:
            skip_reason = config.pre_agent_hook(agent, base_date)
            if skip_reason is not None:
                print(f"[{agent_start}]    ⏭️  {agent}: {skip_reason}")
                success += 1
                if use_job_file and child_job_id:
                    update_job(job_file, job_id=child_job_id, updates={
                        "status": "completed", "completed_at": agent_start,
                        "status_detail": skip_reason,
                    })
                continue

        # プロンプト構築
        prompt = config.build_prompt(agent, base_date)

        if run_kiro_cli(prompt, agent_log, agent_name=agent):
            agent_end = now_jst()
            print(f"[{agent_end}]    ✅ {agent} 完了")
            success += 1
            if use_job_file and child_job_id:
                update_job(job_file, job_id=child_job_id,
                           updates={"status": "completed", "completed_at": agent_end})
        else:
            agent_end = now_jst()
            print(f"[{agent_end}]    ❌ {agent} 失敗（ログ: {agent_log}）")
            print(f"[{agent_end}]    💡 再実行: kiro-cli chat --agent {agent} --trust-all-tools --no-interactive \"{prompt}\"")
            log_error(f"{config.name}-pipeline", agent, "kiro-cli exit non-zero")
            failed += 1
            failed_names.append(agent)
            if use_job_file and child_job_id:
                update_job(job_file, job_id=child_job_id, updates={
                    "status": "failed", "error": "kiro-cli exit non-zero",
                    "completed_at": agent_end,
                })

    # ─── Step 2.5: post_agents_hook ──────────────────────────────
    if config.post_agents_hook:
        config.post_agents_hook(base_date)

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
    notify_log = config.log_dir / "slack-notify.log"
    rotate_log(notify_log, MAX_AGENT_LOG_LINES, keep_lines=100)

    for agent in config.agents:
        # 通知ファイルパス解決
        file_path: Path | None = None

        # resolve_notify_path フックがあれば優先
        if config.resolve_notify_path:
            file_path = config.resolve_notify_path(agent, base_date)

        # フックがNoneを返した場合、テンプレートマップから解決
        if file_path is None:
            template = config.notify_file_map.get(agent, "")
            if not template:
                notify_skipped += 1
                continue
            file_path = HOME / "Documents" / "works" / template.format(date=base_date)

        if not file_path.exists():
            print(f"   ⏭️  {agent}: 出力ファイルなし（スキップ）")
            notify_skipped += 1
            continue

        print(f"[{now_jst()}]    📨 {agent} 通知中...")
        notify_prompt = f"file_path={file_path}"

        if run_kiro_cli(notify_prompt, notify_log, agent_name="slack-notifier"):
            print(f"[{now_jst()}]    ✅ {agent} 通知完了")
            notify_success += 1
        else:
            print(f"[{now_jst()}]    ⚠️  {agent} 通知失敗（レポート作成は成功扱い）")
            log_error(f"{config.name}-pipeline", f"slack-notify:{agent}", "通知失敗")

    notify_end = now_jst()
    print(f"[{notify_end}] 📨 通知完了: ✅{notify_success}件 / ⏭️{notify_skipped}件スキップ")

    # ─── Step 5: post_notify_hook ────────────────────────────────
    if config.post_notify_hook:
        config.post_notify_hook(base_date)

    # ─── Step 6: 完了サマリー ────────────────────────────────────
    final_now = now_jst()
    print(f"[{final_now}] 📊 実行完了: ✅{success}件 / ❌{failed}件 (全{total}件)")
    if failed > 0:
        print(f"[{final_now}]    失敗: {' '.join(failed_names)}")
    if use_job_file and job_file:
        print(f"[{final_now}]    ジョブファイル: {job_file}")
    print(f"[{final_now}] ✅ {label}scoutパイプライン完了（基準日: {base_date}）")

    # スリープ防止解除
    stop_caffeinate(caffeinate_pid)
