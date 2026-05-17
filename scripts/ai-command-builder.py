#!/usr/bin/env python3.12
"""
ai-command-builder: AIコマンド構築ユーティリティ

AI_COMMAND_TYPE に応じた CLI コマンド（claude / kiro-cli）を構築する。
他スクリプトから import して使える関数としても、
単体スクリプトとしても利用可能。

Usage (CLI):
    python3.12 ~/scripts/ai-command-builder.py --prompt "Hello" --agent my-agent
    python3.12 ~/scripts/ai-command-builder.py --prompt "Hello" --type kiro-cli
    python3.12 ~/scripts/ai-command-builder.py --prompt "Hello" --interactive

Usage (import):
    from importlib.machinery import SourceFileLoader
    mod = SourceFileLoader("ai_command_builder",
                           str(Path.home() / "scripts" / "ai-command-builder.py")).load_module()
    cmd = mod.build_ai_command("Hello", agent_name="my-agent")

依存: 標準ライブラリのみ
"""

import argparse
import os
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

SUPPORTED_TYPES = ("claude", "kiro-cli")
DEFAULT_TYPE = "claude"


# ─── 公開関数 ────────────────────────────────────────────────────

def build_ai_command(
    prompt: str,
    *,
    ai_type: str | None = None,
    agent_name: str = "",
    interactive: bool = False,
    session_id: str = "",
    output_format: str = "",
) -> list[str]:
    """AI_COMMAND_TYPE に応じた実行コマンドを構築する。

    Args:
        prompt: AIに渡すプロンプト文字列
        ai_type: "claude" | "kiro-cli"（None の場合は環境変数 AI_COMMAND_TYPE を参照）
        agent_name: エージェント名（省略可）
        interactive: True の場合の挙動:
            - kiro-cli: --no-interactive を付与しない
            - claude: --print を付与しない（対話モードで起動）
        session_id: セッション再開ID（省略可）
            - kiro-cli: --resume-id <id>
            - claude: --resume <id>（指定時は --agent を付与しない）
        output_format: 出力形式（省略可）
            - claude: --output-format <format>（例: "json"）
            - kiro-cli: 未対応（無視される）

    Returns:
        subprocess.run() に渡せるコマンドリスト
    """
    resolved_type = ai_type or os.environ.get("AI_COMMAND_TYPE", DEFAULT_TYPE)

    if resolved_type not in SUPPORTED_TYPES:
        raise ValueError(
            f"未対応の AI_COMMAND_TYPE: {resolved_type!r} "
            f"(対応: {', '.join(SUPPORTED_TYPES)})"
        )

    if resolved_type == "kiro-cli":
        cmd = ["kiro-cli", "chat", "--trust-all-tools"]
        if not interactive:
            cmd.append("--no-interactive")
        if session_id:
            cmd.extend(["--resume-id", session_id])
        elif agent_name:
            cmd.extend(["--agent", agent_name])
        cmd.append(prompt)
        return cmd

    # default: claude code
    cmd = ["claude"]
    if not interactive:
        cmd.append("--print")
    cmd.append("--dangerously-skip-permissions")
    if output_format:
        cmd.extend(["--output-format", output_format])
    if session_id:
        cmd.extend(["--resume", session_id])
    elif agent_name:
        cmd.extend(["--agent", agent_name])
    cmd.append(prompt)
    return cmd


def get_ai_type(override: str | None = None) -> str:
    """現在有効な AI_COMMAND_TYPE を返す。

    Args:
        override: 明示指定（None の場合は環境変数を参照）

    Returns:
        "claude" | "kiro-cli"
    """
    return override or os.environ.get("AI_COMMAND_TYPE", DEFAULT_TYPE)


# ─── CLI エントリポイント ────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI CLI コマンドを構築して表示する",
    )
    parser.add_argument(
        "--prompt", required=True,
        help="AIに渡すプロンプト文字列",
    )
    parser.add_argument(
        "--type", dest="ai_type", choices=SUPPORTED_TYPES, default=None,
        help=f"AI CLI タイプ（省略時: 環境変数 AI_COMMAND_TYPE、デフォルト {DEFAULT_TYPE}）",
    )
    parser.add_argument(
        "--agent", dest="agent_name", default="",
        help="エージェント名（省略可）",
    )
    parser.add_argument(
        "--interactive", action="store_true", default=False,
        help="対話モードで起動（kiro-cli: --no-interactive 省略、claude: --print 省略）",
    )
    parser.add_argument(
        "--session-id", default="",
        help="セッション再開ID（kiro-cli: --resume-id、claude: --resume）",
    )
    parser.add_argument(
        "--output-format", default="",
        help="出力形式（claude: --output-format、例: json）",
    )
    parser.add_argument(
        "--shell-format", action="store_true", default=False,
        help="シェルで実行可能な形式で出力する（引数をクォート）",
    )
    args = parser.parse_args()

    try:
        cmd = build_ai_command(
            args.prompt,
            ai_type=args.ai_type,
            agent_name=args.agent_name,
            interactive=args.interactive,
            session_id=args.session_id,
            output_format=args.output_format,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.shell_format:
        # シェル実行可能形式: プロンプト（最後の引数）をクォート
        parts = cmd[:-1] + [f'"{cmd[-1]}"']
        print(" ".join(parts))
    else:
        # スペース区切り（そのまま）
        print(" ".join(cmd))


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
