#!/usr/bin/env python3.12
"""
run-github-repo-analysis-pipeline: GitHubリポジトリ分析パイプライン

目的:
    GitHubリポジトリを多角的に調査し、統合レポートを生成する。
    各エージェントを独立プロセスとして逐次実行し、コンテキスト汚染を防ぐ。

使い方:
    python3.12 scripts/run-github-repo-analysis-pipeline.py <repo_url>
    python3.12 scripts/run-github-repo-analysis-pipeline.py https://github.com/owner/repo
    python3.12 scripts/run-github-repo-analysis-pipeline.py https://github.com/owner/repo --skip-web --skip-codebase
    python3.12 scripts/run-github-repo-analysis-pipeline.py https://github.com/owner/repo --skip-refs --skip-review

出力: Documents/works/scout_reports/github_repo_analysis/{date}_{slug}_analysis.md
依存: kiro-cli または claude (AI_COMMAND_TYPE環境変数で切替), python3.12, gh (GitHub CLI)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _pipeline_common import run_ai_command, run_slack_notify, load_env

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
OUTPUT_BASE = HOME / "Documents" / "works" / "scout_reports" / "github_repo_analysis"
LOG_DIR = HOME / "logs" / "jobs" / "github_repo_analysis"
MAX_LOG_LINES = 500


# ─── ユーティリティ ──────────────────────────────────────────────

def now_jst() -> str:
    """現在時刻をJST ISO形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def today_jst() -> str:
    """今日の日付をYYYY-MM-DD形式で返す。"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d")


def make_slug(owner: str, repo: str) -> str:
    """owner/repoからファイル名用スラッグを生成する。"""
    raw = f"{owner}-{repo}"
    return re.sub(r"[._]", "-", raw).lower()


def parse_repo_url(url: str) -> tuple[str, str]:
    """リポジトリURLからowner, repoを抽出する。"""
    # https://github.com/owner/repo or owner/repo
    match = re.match(r"(?:https?://github\.com/)?([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        print(f"エラー: リポジトリURLを解析できません: {url}", file=sys.stderr)
        sys.exit(1)
    return match.group(1), match.group(2)


def rotate_log(log_file: Path, max_lines: int, keep_lines: int = 100) -> None:
    """ログファイルが max_lines を超えていたら末尾 keep_lines 行に切り詰める。"""
    if not log_file.exists():
        return
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > max_lines:
        log_file.write_text("\n".join(lines[-keep_lines:]) + "\n", encoding="utf-8")


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


def _log_agent_header(log_file: Path, agent_name: str, prompt: str) -> None:
    """ログファイルにエージェント実行ヘッダを追記する。"""
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"[{now_jst()}] Agent: {agent_name}\n")
        f.write(f"Prompt: {prompt[:200]}...\n")
        f.write(f"{'='*60}\n")


def extract_machine_data(file_path: Path) -> dict:
    """一時ファイルから機械可読データを抽出する。"""
    result = subprocess.run(
        ["python3.12", str(SCRIPTS_DIR / "extract-repo-analysis-data.py"), str(file_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠️  機械可読データ抽出失敗: {result.stderr.strip()}", file=sys.stderr)
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  ⚠️  JSON解析失敗", file=sys.stderr)
        return {}


# ─── パイプラインステップ ────────────────────────────────────────

def step1_github_analysis(
    owner: str, repo: str, slug: str, base_date: str, log_file: Path,
) -> Path | None:
    """Step 1: GitHub API調査。"""
    output_path = OUTPUT_BASE / "tmp" / f"{slug}_github.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        f"対象リポジトリ: {owner}/{repo} "
        f"出力先: {output_path}"
    )
    _log_agent_header(log_file, "github-repo-analyst", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="github-repo-analyst")
    if ok and output_path.exists():
        return output_path
    return None


def step2_refs_analysis(
    owner: str, repo: str, slug: str, base_date: str,
    machine_data: dict, log_file: Path,
) -> Path | None:
    """Step 2: 参照先リポジトリ調査。"""
    # 推奨リポジトリを抽出
    related = machine_data.get("related_repositories", {})
    recommended = related.get("recommended_for_deep_analysis", [])
    fork_source = related.get("fork_source")

    repos_to_check: list[str] = []
    if fork_source:
        repos_to_check.append(fork_source)
    for item in recommended[:3]:
        if isinstance(item, dict):
            r = item.get("repo", "")
            if r and r not in repos_to_check:
                repos_to_check.append(r)
        elif isinstance(item, str):
            if item not in repos_to_check:
                repos_to_check.append(item)

    if not repos_to_check:
        print(f"[{now_jst()}]    ⏭️  参照先リポジトリなし（スキップ）")
        return None

    output_path = OUTPUT_BASE / "tmp" / f"{slug}_refs.md"
    repos_text = "\n".join(f"- {r}" for r in repos_to_check[:3])
    prompt = (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        f"以下のリポジトリを概要レベルで調査してください（README・構造・依存関係の概要）:\n"
        f"{repos_text}\n"
        f"出力先: {output_path}"
    )
    _log_agent_header(log_file, "github-repo-analyst", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="github-repo-analyst")
    if ok and output_path.exists():
        return output_path
    return None


def step3_web_search(
    owner: str, repo: str, slug: str, base_date: str,
    machine_data: dict, log_file: Path,
) -> Path | None:
    """Step 3: Web調査。"""
    output_path = OUTPUT_BASE / "tmp" / f"{slug}_web.md"

    # キーワード抽出
    keywords = machine_data.get("web_search_keywords", {})
    primary = keywords.get("primary", f"{owner}/{repo}")
    secondary = keywords.get("secondary", [])
    competitors = keywords.get("competitors", [])
    ecosystem = keywords.get("ecosystem", "")

    basic_info = machine_data.get("basic_info", {})
    description = basic_info.get("description", "")

    secondary_text = ", ".join(secondary) if secondary else ""
    competitors_text = ", ".join(competitors) if competitors else ""

    prompt = (
        f"基準日は {base_date} です。"
        f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
        f"以下のテーマについてWeb調査を行ってください。\n"
        f"テーマ: {primary} のエコシステム・競合・導入事例\n"
        f"リポジトリ: {owner}/{repo}\n"
        f"説明: {description}\n"
        f"キーワード: {secondary_text}\n"
        f"競合: {competitors_text}\n"
        f"エコシステム: {ecosystem}\n"
        f"purpose: tech_selection\n"
        f"出力先: {output_path}"
    )
    _log_agent_header(log_file, "web-searcher", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="web-searcher")
    if ok and output_path.exists():
        return output_path
    return None


def step4_code_analysis(
    owner: str, repo: str, slug: str, base_date: str,
    machine_data: dict, log_file: Path,
) -> Path | None:
    """Step 4: コードベース分析。"""
    output_path = OUTPUT_BASE / "tmp" / f"{slug}_codebase.md"

    basic_info = machine_data.get("basic_info", {})
    default_branch = basic_info.get("default_branch", "main")
    language = basic_info.get("language", "")

    hints = machine_data.get("code_analysis_hints", {})
    source_dirs = hints.get("source_dirs", [])
    test_dirs = hints.get("test_dirs", [])
    config_files = hints.get("config_files", [])
    entry_points = hints.get("entry_points", [])

    hints_text = ""
    if source_dirs:
        hints_text += f"ソースディレクトリ: {', '.join(source_dirs)}\n"
    if test_dirs:
        hints_text += f"テストディレクトリ: {', '.join(test_dirs)}\n"
    if config_files:
        hints_text += f"設定ファイル: {', '.join(config_files)}\n"
    if entry_points:
        hints_text += f"エントリポイント: {', '.join(entry_points)}\n"

    prompt = (
        f"以下のリポジトリのコードベースを分析してください。\n"
        f"リポジトリ: {owner}/{repo}\n"
        f"デフォルトブランチ: {default_branch}\n"
        f"主要言語: {language}\n"
        f"{hints_text}"
        f"出力先: {output_path}"
    )
    _log_agent_header(log_file, "code-analyst", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="code-analyst")
    if ok and output_path.exists():
        return output_path
    return None


def step5_report_integration(
    owner: str, repo: str, slug: str, base_date: str,
    tmp_files: list[Path], log_file: Path,
) -> Path | None:
    """Step 5: レポート統合。"""
    output_path = OUTPUT_BASE / f"{base_date}_{slug}_analysis.md"
    format_file = HOME / ".shared-ai" / "interfaces" / "github-repo-analysis-report-format.md"

    input_files = ",".join(str(f) for f in tmp_files if f.exists())

    prompt = (
        f"以下の中間ファイルを統合してレポートを作成してください。\n"
        f"入力ファイル: {input_files}\n"
        f"出力先: {output_path}\n"
        f"フォーマット指示ファイル: {format_file}\n"
        f"対象期間: {base_date}"
    )
    _log_agent_header(log_file, "markdown-reporter", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="markdown-reporter")
    if ok and output_path.exists():
        return output_path
    return None


def step6_review(report_path: Path, log_file: Path) -> bool:
    """Step 6: 品質レビュー。"""
    prompt = (
        f"以下のレポートファイルをレビューしてください。"
        f"レビュー: 1段階目から開始してください。"
        f"対象ファイル: {report_path}"
    )
    _log_agent_header(log_file, "agent-output-reviewer", prompt)
    ok, _ = run_ai_command(prompt, log_file, agent_name="agent-output-reviewer")
    return ok


def step7_slack_notify(report_path: Path, log_file: Path) -> bool:
    """Step 7: Slack通知。"""
    return run_slack_notify(report_path, log_file, thread="compact")


# ─── 一時ファイルクリーンアップ ──────────────────────────────────

def cleanup_tmp_files(slug: str) -> None:
    """一時ファイルを削除する。"""
    tmp_dir = OUTPUT_BASE / "tmp"
    patterns = [
        tmp_dir / f"{slug}_github.md",
        tmp_dir / f"{slug}_refs.md",
        tmp_dir / f"{slug}_web.md",
        tmp_dir / f"{slug}_codebase.md",
    ]
    for p in patterns:
        if p.exists():
            p.unlink()
            print(f"  🗑️  削除: {p.name}")


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHubリポジトリ分析パイプライン",
    )
    parser.add_argument("repo_url", help="リポジトリURL (https://github.com/owner/repo)")
    parser.add_argument("--skip-refs", action="store_true", help="Step 2（参照先調査）をスキップ")
    parser.add_argument("--skip-web", action="store_true", help="Step 3（Web調査）をスキップ")
    parser.add_argument("--skip-codebase", action="store_true", help="Step 4（コードベース分析）をスキップ")
    parser.add_argument("--skip-review", action="store_true", help="Step 6（品質レビュー）をスキップ")
    parser.add_argument("--skip-notify", action="store_true", help="Step 7（Slack通知）をスキップ")
    parser.add_argument("--no-cleanup", action="store_true", help="一時ファイルを削除しない")
    args = parser.parse_args()

    owner, repo = parse_repo_url(args.repo_url)
    slug = make_slug(owner, repo)
    base_date = today_jst()

    # ディレクトリ準備
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{slug}.log"
    rotate_log(log_file, MAX_LOG_LINES)

    # 環境準備
    load_env()
    caffeinate_pid = start_caffeinate()

    print(f"[{now_jst()}] 🔬 GitHub Repo Analysis Pipeline 起動")
    print(f"[{now_jst()}]    リポジトリ: {owner}/{repo}")
    print(f"[{now_jst()}]    基準日: {base_date}")
    print(f"[{now_jst()}]    スラッグ: {slug}")
    print()

    # ─── Step 1: GitHub API調査 ──────────────────────────────────
    print(f"[{now_jst()}] Step 1: GitHub API調査...")
    github_file = step1_github_analysis(owner, repo, slug, base_date, log_file)
    if not github_file:
        print(f"[{now_jst()}]    ❌ GitHub API調査失敗。パイプライン中断。")
        stop_caffeinate(caffeinate_pid)
        sys.exit(1)
    print(f"[{now_jst()}]    ✅ 完了: {github_file.name}")

    # 機械可読データ抽出
    print(f"[{now_jst()}]    📊 機械可読データ抽出中...")
    machine_data = extract_machine_data(github_file)
    if not machine_data:
        print(f"[{now_jst()}]    ⚠️  機械可読データなし（後続ステップはデフォルト値で実行）")

    # ─── Step 2: 参照先リポジトリ調査 ────────────────────────────
    refs_file: Path | None = None
    if args.skip_refs:
        print(f"[{now_jst()}] Step 2: 参照先リポジトリ調査（スキップ）")
    else:
        print(f"[{now_jst()}] Step 2: 参照先リポジトリ調査...")
        refs_file = step2_refs_analysis(owner, repo, slug, base_date, machine_data, log_file)
        if refs_file:
            print(f"[{now_jst()}]    ✅ 完了: {refs_file.name}")
        else:
            print(f"[{now_jst()}]    ⏭️  スキップ（対象なしまたは失敗）")

    # ─── Step 3: Web調査 ─────────────────────────────────────────
    web_file: Path | None = None
    if args.skip_web:
        print(f"[{now_jst()}] Step 3: Web調査（スキップ）")
    else:
        print(f"[{now_jst()}] Step 3: Web調査...")
        # 通知用に環境変数を切り替え（web-searcherはSlack不要だが念のため）
        web_file = step3_web_search(owner, repo, slug, base_date, machine_data, log_file)
        if web_file:
            print(f"[{now_jst()}]    ✅ 完了: {web_file.name}")
        else:
            print(f"[{now_jst()}]    ⚠️  Web調査失敗（続行）")

    # ─── Step 4: コードベース分析 ────────────────────────────────
    codebase_file: Path | None = None
    if args.skip_codebase:
        print(f"[{now_jst()}] Step 4: コードベース分析（スキップ）")
    else:
        print(f"[{now_jst()}] Step 4: コードベース分析...")
        codebase_file = step4_code_analysis(
            owner, repo, slug, base_date, machine_data, log_file,
        )
        if codebase_file:
            print(f"[{now_jst()}]    ✅ 完了: {codebase_file.name}")
        else:
            print(f"[{now_jst()}]    ⚠️  コードベース分析失敗（続行）")

    # ─── Step 5: レポート統合 ────────────────────────────────────
    print(f"[{now_jst()}] Step 5: レポート統合...")
    tmp_files = [f for f in [github_file, refs_file, web_file, codebase_file] if f]
    report_path = step5_report_integration(
        owner, repo, slug, base_date, tmp_files, log_file,
    )
    if not report_path:
        print(f"[{now_jst()}]    ❌ レポート統合失敗。パイプライン中断。")
        stop_caffeinate(caffeinate_pid)
        sys.exit(1)
    print(f"[{now_jst()}]    ✅ 完了: {report_path.name}")

    # ─── Step 6: 品質レビュー ────────────────────────────────────
    if args.skip_review:
        print(f"[{now_jst()}] Step 6: 品質レビュー（スキップ）")
    else:
        print(f"[{now_jst()}] Step 6: 品質レビュー...")
        if step6_review(report_path, log_file):
            print(f"[{now_jst()}]    ✅ レビュー完了")
        else:
            print(f"[{now_jst()}]    ⚠️  レビュー失敗（レポートはそのまま使用）")

    # ─── Step 7: Slack通知 ───────────────────────────────────────
    if args.skip_notify:
        print(f"[{now_jst()}] Step 7: Slack通知（スキップ）")
    else:
        print(f"[{now_jst()}] Step 7: Slack通知...")
        if step7_slack_notify(report_path, log_file):
            print(f"[{now_jst()}]    ✅ 通知完了")
        else:
            print(f"[{now_jst()}]    ⚠️  通知失敗（レポート作成は成功扱い）")

    # ─── クリーンアップ ──────────────────────────────────────────
    if not args.no_cleanup:
        print(f"[{now_jst()}] 🗑️  一時ファイルクリーンアップ...")
        cleanup_tmp_files(slug)

    # ─── 完了 ────────────────────────────────────────────────────
    stop_caffeinate(caffeinate_pid)
    print()
    print(f"[{now_jst()}] ✅ パイプライン完了")
    print(f"[{now_jst()}]    レポート: {report_path}")
    print(f"[{now_jst()}]    ログ: {log_file}")


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
