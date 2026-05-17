#!/usr/bin/env python3.12
"""
check-env: 環境変数の設定状況チェック

目的:
    必須・オプション環境変数が .zshrc に設定されているか、
    platform-commands.sh の source-env リストに含まれているかを検証する。
    不足がある場合は修正手順を表示する。

使い方:
    python3.12 scripts/check-env.py          # 全チェック
    python3.12 scripts/check-env.py --quiet  # エラー時のみ出力

終了コード:
    0: 必須環境変数が全て設定済み
    1: 必須環境変数に不足あり
"""

import os
import re
import sys
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"

# シェルRC候補
SHELL_RC_CANDIDATES = [
    HOME / ".zshrc",
    HOME / ".bashrc",
]

# 必須環境変数（未設定時はエラー終了）
REQUIRED_VARS = [
    {
        "name": "MY_SLACK_OAUTH_TOKEN",
        "description": "Slack Bot Token（xoxb-...）",
        "used_by": "run-slack-dispatch-router.py, notify-slack.py",
    },
    {
        "name": "SLACK_DISPATCH_DM_CHANNEL",
        "description": "ディスパッチ対象のSlack DMチャンネルID",
        "used_by": "run-slack-dispatch-router.py, notify-slack.py",
    },
    {
        "name": "SLACK_DISPATCH_TARGET_USER",
        "description": "ディスパッチ対象のSlackユーザーID",
        "used_by": "run-slack-dispatch-router.py",
    },
]

# オプション環境変数（未設定でも警告のみ）
OPTIONAL_VARS = [
    {
        "name": "SLACK_REFERENCE_BOT_TOKEN",
        "description": "Slack参照用Bot Token",
        "used_by": "MCP経由（slack-reference）",
    },
    {
        "name": "SLACK_REFERENCE_TEAM_ID",
        "description": "Slack参照用チームID",
        "used_by": "MCP経由（slack-reference）",
    },
    {
        "name": "GH_REFERENCE_TOKEN",
        "description": "GitHub Personal Access Token",
        "used_by": "MCP経由（github）",
    },
    {
        "name": "DEVELOPER_AI_NOTION_TOKEN",
        "description": "Notion API トークン",
        "used_by": "MCP経由（notion）",
    },
    {
        "name": "GITHUB_ORG_NAME",
        "description": "GitHub Organization名",
        "used_by": "run-github-org-trend-scout-pipeline.py",
    },
    {
        "name": "AI_COMMAND_TYPE",
        "description": "AI CLIの種類（claude or kiro-cli）",
        "used_by": "run-slack-dispatch-router.py, _pipeline_common.py, dispatch-agent-wrapper.py",
    },
]


# ─── チェックロジック ─────────────────────────────────────────────

def find_shell_rc() -> Path | None:
    """使用中のシェルRCファイルを特定する。"""
    for rc in SHELL_RC_CANDIDATES:
        if rc.exists():
            return rc
    return None


def get_exported_vars_in_rc(rc_path: Path) -> set[str]:
    """シェルRCファイルから export されている変数名を抽出する。"""
    try:
        content = rc_path.read_text(encoding="utf-8")
    except OSError:
        return set()

    # export VAR=value パターンを抽出
    pattern = re.compile(r"^export\s+([A-Z_][A-Z0-9_]*)=", re.MULTILINE)
    return set(pattern.findall(content))


def get_source_env_vars() -> set[str]:
    """platform-commands.sh の source-env セクションから管理対象変数を抽出する。"""
    if not PLATFORM_CMD.exists():
        return set()

    try:
        content = PLATFORM_CMD.read_text(encoding="utf-8")
    except OSError:
        return set()

    # grep -E パターンから変数名を抽出
    # パターン例: '^export (VAR1|VAR2|VAR3)='
    pattern = re.compile(
        r"grep\s+-E\s+['\"].*?\(([^)]+)\).*?['\"]", re.DOTALL
    )
    matches = pattern.findall(content)

    vars_set: set[str] = set()
    for match in matches:
        # パイプ区切りの変数名を分割
        vars_set.update(v.strip() for v in match.split("|") if v.strip())

    return vars_set


def check_env(quiet: bool = False) -> bool:
    """環境変数の設定状況をチェックする。

    Args:
        quiet: True の場合、エラー時のみ出力

    Returns:
        True: 必須環境変数が全て設定済み
        False: 必須環境変数に不足あり
    """
    rc_path = find_shell_rc()
    rc_vars = get_exported_vars_in_rc(rc_path) if rc_path else set()
    source_env_vars = get_source_env_vars()

    has_error = False
    needs_source = False
    issues: list[str] = []

    if not quiet:
        print("=== 環境変数チェック ===\n")
        if rc_path:
            print(f"シェルRC: {rc_path}")
        else:
            print("⚠️  シェルRCファイルが見つかりません")
        print()

    # 必須変数チェック
    if not quiet:
        print("[必須環境変数]")

    for var in REQUIRED_VARS:
        name = var["name"]
        in_env = bool(os.environ.get(name))
        in_rc = name in rc_vars
        in_source_env = name in source_env_vars

        if in_env and in_rc and in_source_env:
            if not quiet:
                print(f"  ✅ {name}: OK")
        elif in_rc and in_source_env and not in_env:
            # .zshrc に定義済み + source-env に登録済み → シェル再読み込みで解決
            if not quiet:
                print(f"  ⚠️  {name}: 現在のシェルに未反映（.zshrc/source-env は設定済み）")
            needs_source = True
        else:
            has_error = True
            problems: list[str] = []
            if not in_env:
                problems.append("現在のシェルに未設定")
            if not in_rc:
                problems.append(f"{rc_path or '~/.zshrc'} に未定義")
            if not in_source_env:
                problems.append("source-env リストに未登録")

            print(f"  ❌ {name}: {', '.join(problems)}")
            print(f"     用途: {var['description']}")
            print(f"     使用: {var['used_by']}")

            # 修正手順
            if not in_rc:
                issues.append(
                    f"  ~/.zshrc に追加:\n"
                    f"    export {name}=<値を設定>"
                )
            if not in_source_env:
                issues.append(
                    f"  scripts/platform-commands.sh の source-env セクション内\n"
                    f"  grep パターン（2箇所: eval行とenv行）に {name} を追加"
                )

    if not quiet:
        print()

    # オプション変数チェック
    if not quiet:
        print("[オプション環境変数]")

    for var in OPTIONAL_VARS:
        name = var["name"]
        in_env = bool(os.environ.get(name))
        in_rc = name in rc_vars
        in_source_env = name in source_env_vars

        if in_env and in_rc and in_source_env:
            if not quiet:
                print(f"  ✅ {name}: OK")
        else:
            problems = []
            if not in_env:
                problems.append("未設定")
            if not in_rc:
                problems.append(f"{rc_path or '~/.zshrc'} に未定義")
            if not in_source_env:
                problems.append("source-env リストに未登録")

            if not quiet:
                print(f"  ⚠️  {name}: {', '.join(problems)}")
                print(f"     用途: {var['description']}")

            # オプションでも source-env 漏れは修正手順を出す
            if in_rc and not in_source_env:
                issues.append(
                    f"  scripts/platform-commands.sh の source-env セクション内\n"
                    f"  grep パターン（2箇所: eval行とenv行）に {name} を追加"
                )

    # 修正手順の出力
    if issues or needs_source:
        print()
        print("─── 修正手順 ───")
        print()
        for issue in issues:
            print(issue)
            print()
        if needs_source:
            print("  シェルを再起動するか `source ~/.zshrc` を実行してください。")
            print()
        if issues:
            print("修正後、シェルを再起動するか `source ~/.zshrc` を実行してください。")

    if not quiet:
        print()
        if has_error:
            print("❌ 必須環境変数に不足があります")
        else:
            print("✅ 必須環境変数は全て設定済み")

    return not has_error


# ─── エントリポイント ────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="環境変数の設定状況をチェックする"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="エラー時のみ出力",
    )
    args = parser.parse_args()

    ok = check_env(quiet=args.quiet)
    sys.exit(0 if ok else 1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
