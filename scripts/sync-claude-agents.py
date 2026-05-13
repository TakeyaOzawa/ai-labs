#!/usr/bin/env python3.12
"""
sync-claude-agents: kiroエージェント定義からclaude code用エージェントを生成する

目的:
    ~/.kiro/agents/*.json と ~/.shared-ai/prompts/*.md を読み込み、
    ~/.claude/agents/*.md (frontmatter付きMarkdown) を生成する。
    AI_COMMAND_TYPE=claude で実行するパイプラインのために、
    kiroのエージェント定義をclaude code形式に橋渡しする。

使い方:
    python3.12 scripts/sync-claude-agents.py
    python3.12 scripts/sync-claude-agents.py --dry-run
    python3.12 scripts/sync-claude-agents.py --agent slack-notifier
    python3.12 scripts/sync-claude-agents.py --prune

出力: ~/.claude/agents/<name>.md
"""

import argparse
import json
import sys
from pathlib import Path

KIRO_AGENTS_DIR = Path.home() / ".kiro" / "agents"
CLAUDE_AGENTS_DIR = Path.home() / ".claude" / "agents"

# kiroのツールカテゴリ → claudeのツール名
# omit: 詳細パス/コマンド制限はclaude側で再現不能なため省略
TOOL_MAP: dict[str, list[str]] = {
    "read": ["Read", "Glob", "Grep"],
    "write": ["Write", "Edit"],
    "shell": ["Bash"],
    "web": ["WebSearch", "WebFetch"],
}

MODEL_MAP: dict[str, str] = {
    "claude-sonnet-4": "sonnet",
    "claude-opus-4": "opus",
    "claude-haiku-4": "haiku",
}


def resolve_prompt_path(kiro_agent_path: Path, prompt_field: str) -> Path | None:
    """kiro agent JSONの`prompt`フィールドからプロンプトファイルパスを解決する。"""
    if not prompt_field.startswith("file://"):
        return None
    rel = prompt_field.removeprefix("file://")
    return (kiro_agent_path.parent / rel).resolve()


def map_tools(kiro_tools: list[str]) -> list[str]:
    """kiroのツールカテゴリをclaudeのツール名にマッピングする(重複除去)。"""
    seen: set[str] = set()
    result: list[str] = []
    for kt in kiro_tools:
        for ct in TOOL_MAP.get(kt, []):
            if ct not in seen:
                seen.add(ct)
                result.append(ct)
    return result


def build_markdown(kiro_data: dict, prompt_body: str) -> str:
    """claudeエージェント.md形式を構築する。

    tools欄の方針:
        - kiroのincludeMcpJson=trueの場合: tools欄を省略(全ツール継承)。
          MCPツール名はサーバ依存で精密マッピング困難なため、
          省略してclaude側のMCP設定をそのまま使えるようにする。
        - includeMcpJson=falseの場合: kiroのカテゴリをclaudeツール名に
          マッピングして列挙し、不要な能力を持たせないようにする。
    """
    name = kiro_data["name"]
    description = (kiro_data.get("description") or "").replace("\n", " ").strip()
    model = MODEL_MAP.get(kiro_data.get("model", ""), "sonnet")

    include_mcp = kiro_data.get("includeMcpJson", False)
    tools = [] if include_mcp else map_tools(kiro_data.get("tools", []))

    lines = ["---", f"name: {name}"]
    if description:
        lines.append(f"description: {description}")
    lines.append(f"model: {model}")
    if tools:
        lines.append(f"tools: {', '.join(tools)}")
    lines.append("---")
    lines.append("")
    lines.append(prompt_body.rstrip())
    return "\n".join(lines) + "\n"


def convert_agent(kiro_path: Path) -> tuple[str, str] | None:
    """1つのkiroエージェントを変換する。Returns (name, markdown) or None。"""
    try:
        data = json.loads(kiro_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  {kiro_path.name}: 読み込み失敗 ({e})", file=sys.stderr)
        return None

    name = data.get("name")
    if not name:
        print(f"⚠️  {kiro_path.name}: name未設定", file=sys.stderr)
        return None

    prompt_field = data.get("prompt", "")
    prompt_path = resolve_prompt_path(kiro_path, prompt_field)
    if not prompt_path or not prompt_path.exists():
        print(f"⚠️  {name}: プロンプトファイル未検出 ({prompt_field})", file=sys.stderr)
        return None

    prompt_body = prompt_path.read_text(encoding="utf-8")
    return name, build_markdown(data, prompt_body)


def main() -> int:
    parser = argparse.ArgumentParser(description="kiro→claude agent sync")
    parser.add_argument("--dry-run", action="store_true",
                        help="出力先に書き込まず変換結果を標準出力に表示")
    parser.add_argument("--agent",
                        help="特定エージェント名のみ変換(例: --agent slack-notifier)")
    parser.add_argument("--prune", action="store_true",
                        help="kiro側に存在しないclaudeエージェント.mdを削除する"
                             "(--agent指定時は無効)")
    args = parser.parse_args()

    if not KIRO_AGENTS_DIR.exists():
        print(f"❌ kiroエージェントディレクトリ未検出: {KIRO_AGENTS_DIR}",
              file=sys.stderr)
        return 1

    if not args.dry_run:
        CLAUDE_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    skipped = 0
    converted_names: list[str] = []

    for kiro_path in sorted(KIRO_AGENTS_DIR.glob("*.json")):
        if kiro_path.name == "agent_config.json.example":
            continue
        if args.agent and kiro_path.stem != args.agent:
            continue

        result = convert_agent(kiro_path)
        if result is None:
            skipped += 1
            continue
        name, content = result
        out_path = CLAUDE_AGENTS_DIR / f"{name}.md"

        if args.dry_run:
            print(f"=== {out_path} ===")
            print(content)
        else:
            out_path.write_text(content, encoding="utf-8")
        success += 1
        converted_names.append(name)

    print(f"✅ 変換: {success}件 / ⏭️ スキップ: {skipped}件", file=sys.stderr)
    if not args.dry_run and success > 0:
        print(f"   出力先: {CLAUDE_AGENTS_DIR}", file=sys.stderr)
        print(f"   生成: {', '.join(converted_names)}", file=sys.stderr)

    if args.prune and not args.agent:
        prune_orphans(args.dry_run)

    return 0


def collect_kiro_agent_names() -> set[str]:
    """kiro側に存在する全エージェントのname集合を返す。

    parse失敗したJSONは「kiroに存在する」とみなしてname=stemで含める。
    壊れたJSONを理由にclaude側を消してしまう事故を防ぐため。
    """
    names: set[str] = set()
    for kiro_path in KIRO_AGENTS_DIR.glob("*.json"):
        if kiro_path.name == "agent_config.json.example":
            continue
        try:
            data = json.loads(kiro_path.read_text(encoding="utf-8"))
            name = data.get("name") or kiro_path.stem
        except (json.JSONDecodeError, OSError):
            name = kiro_path.stem
        names.add(name)
    return names


def prune_orphans(dry_run: bool) -> None:
    """kiro側に存在しないclaudeエージェント.mdを削除する。"""
    if not CLAUDE_AGENTS_DIR.exists():
        return
    kiro_names = collect_kiro_agent_names()
    orphans = [
        p for p in sorted(CLAUDE_AGENTS_DIR.glob("*.md"))
        if p.stem not in kiro_names
    ]
    if not orphans:
        print("🧹 削除対象なし", file=sys.stderr)
        return

    for p in orphans:
        if dry_run:
            print(f"🗑️  [dry-run] 削除予定: {p}", file=sys.stderr)
        else:
            p.unlink()
            print(f"🗑️  削除: {p}", file=sys.stderr)
    print(f"🧹 削除: {len(orphans)}件", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
