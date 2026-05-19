#!/usr/bin/env python3.12
"""
ai-cli-utils: AI CLI ユーティリティモジュール

AI_COMMAND_TYPE に応じた CLI コマンド構築、エージェント一覧スキャンなど、
AI CLI（claude / kiro-cli）操作に関する共通機能を提供する。
他スクリプトから import して使える関数群としても、
単体スクリプトとしても利用可能。

Usage (CLI):
    python3.12 ~/scripts/ai-cli-utils.py build --prompt "Hello" --agent my-agent
    python3.12 ~/scripts/ai-cli-utils.py build --prompt "Hello" --type kiro-cli
    python3.12 ~/scripts/ai-cli-utils.py build --prompt "Hello" --interactive
    python3.12 ~/scripts/ai-cli-utils.py scan-agents

Usage (import):
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("ai_cli_utils",
                                    str(Path.home() / "scripts" / "ai-cli-utils.py"))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    cmd = mod.build_ai_command("Hello", agent_name="my-agent")
    agents = mod.scan_agents()

依存: 標準ライブラリのみ
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import json
import os

# ─── 定数 ────────────────────────────────────────────────────────

SUPPORTED_TYPES = ("claude", "kiro-cli")
DEFAULT_TYPE = "claude"

HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent.parent
KIRO_AGENTS_DIR = HOME / ".kiro" / "agents"
CLAUDE_AGENTS_DIR = HOME / ".claude" / "agents"


# ─── 公開関数: コマンド構築 ──────────────────────────────────────

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
        cmd.append("--")
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
    cmd.append("--")
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


# ─── 公開関数: エージェント一覧 ─────────────────────────────────

def scan_agents(
    *,
    include_pipelines: bool = True,
    excluded_pipelines: set[str] | None = None,
) -> list[dict]:
    """利用可能なエージェント・パイプライン一覧を取得する。

    AI_COMMAND_TYPE に応じて .kiro/agents/ または .claude/agents/ をスキャンし、
    さらに scripts/run-*-pipeline.py も対象として追加する。

    Args:
        include_pipelines: パイプラインスクリプトも含めるか（デフォルト True）
        excluded_pipelines: 除外するパイプライン名のセット（stem）

    Returns:
        [{"name": "...", "description": "..."}, ...] のリスト
    """
    if excluded_pipelines is None:
        excluded_pipelines = {
            "run-github-repo-analysis-pipeline",
            "run-poc-planner-pipeline",
            "run-freshness-pipeline",
        }

    ai_type = get_ai_type()
    agents: list[dict] = []

    if ai_type == "kiro-cli":
        # .kiro/agents/*.json をスキャン
        if KIRO_AGENTS_DIR.exists():
            for f in sorted(KIRO_AGENTS_DIR.glob("*.json")):
                if f.name.startswith("agent_config"):
                    continue
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    name = data.get("name", f.stem)
                    desc = data.get("description", "")
                    agents.append({"name": name, "description": desc})
                except (json.JSONDecodeError, OSError):
                    continue
    else:
        # .claude/agents/*.md をスキャン（ファイル名がエージェント名）
        if CLAUDE_AGENTS_DIR.exists():
            for f in sorted(CLAUDE_AGENTS_DIR.glob("*.md")):
                name = f.stem
                # 先頭行からdescriptionを抽出
                try:
                    first_lines = f.read_text(encoding="utf-8").split("\n")[:5]
                    desc = ""
                    for line in first_lines:
                        if line.startswith("# "):
                            desc = line[2:].strip()
                            break
                    agents.append({"name": name, "description": desc})
                except OSError:
                    agents.append({"name": name, "description": ""})

    # run-*-pipeline.py をスキャン
    if include_pipelines:
        for f in sorted((SCRIPTS_DIR / "pipelines").glob("run-*-pipeline.py")):
            name = f.stem
            if name in excluded_pipelines:
                continue
            desc = _extract_pipeline_description(f)
            agents.append({"name": name, "description": desc})

    return agents


def _extract_pipeline_description(script_path: Path) -> str:
    """パイプラインスクリプトの docstring から説明行を抽出する。

    "name: description" 形式の最初の有意義な行を返す。
    """
    try:
        lines = script_path.read_text(encoding="utf-8").splitlines()
        in_docstring = False
        for line in lines[:25]:
            stripped = line.strip()
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_docstring = True
                continue
            if stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
                # "name: description" 形式ならコロン以降を返す
                if ": " in stripped:
                    return stripped.split(": ", 1)[1].strip()
                return stripped
    except OSError:
        pass
    return ""


# ─── CLI エントリポイント ────────────────────────────────────────

def _cmd_build(args: argparse.Namespace) -> None:
    """build サブコマンド: コマンドを構築して表示する。"""
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
        parts = cmd[:-1] + [f'"{cmd[-1]}"']
        print(" ".join(parts))
    else:
        print(" ".join(cmd))


def _cmd_scan_agents(args: argparse.Namespace) -> None:
    """scan-agents サブコマンド: エージェント一覧を表示する。"""
    agents = scan_agents()
    if args.json_output:
        print(json.dumps(agents, ensure_ascii=False, indent=2))
    else:
        for a in agents:
            desc = f"  ({a['description']})" if a["description"] else ""
            print(f"  - {a['name']}{desc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI CLI ユーティリティ（コマンド構築・エージェント一覧）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build サブコマンド
    build_parser = subparsers.add_parser("build", help="AI CLI コマンドを構築して表示")
    build_parser.add_argument(
        "--prompt", required=True,
        help="AIに渡すプロンプト文字列",
    )
    build_parser.add_argument(
        "--type", dest="ai_type", choices=SUPPORTED_TYPES, default=None,
        help=f"AI CLI タイプ（省略時: 環境変数 AI_COMMAND_TYPE、デフォルト {DEFAULT_TYPE}）",
    )
    build_parser.add_argument(
        "--agent", dest="agent_name", default="",
        help="エージェント名（省略可）",
    )
    build_parser.add_argument(
        "--interactive", action="store_true", default=False,
        help="対話モードで起動（kiro-cli: --no-interactive 省略、claude: --print 省略）",
    )
    build_parser.add_argument(
        "--session-id", default="",
        help="セッション再開ID（kiro-cli: --resume-id、claude: --resume）",
    )
    build_parser.add_argument(
        "--output-format", default="",
        help="出力形式（claude: --output-format、例: json）",
    )
    build_parser.add_argument(
        "--shell-format", action="store_true", default=False,
        help="シェルで実行可能な形式で出力する（引数をクォート）",
    )
    build_parser.set_defaults(func=_cmd_build)

    # scan-agents サブコマンド
    scan_parser = subparsers.add_parser("scan-agents", help="利用可能なエージェント一覧を表示")
    scan_parser.add_argument(
        "--json", dest="json_output", action="store_true", default=False,
        help="JSON形式で出力する",
    )
    scan_parser.set_defaults(func=_cmd_scan_agents)

    args = parser.parse_args()
    args.func(args)



if __name__ == "__main__":
    main()
