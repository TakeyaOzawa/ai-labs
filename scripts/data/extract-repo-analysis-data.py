#!/usr/bin/env python3.12
"""
extract-repo-analysis-data: github-repo-analyst出力から機械可読データを抽出する

目的:
    github-repo-analystが生成した一時ファイルから
    "# --- machine-readable-data ---" セクションのYAMLを抽出し、
    JSONとして標準出力に書き出す。
    パイプラインスクリプトが後続エージェントへの入力を構築するために使用する。

使い方:
    python3.12 scripts/extract-repo-analysis-data.py <input_file>
    python3.12 scripts/extract-repo-analysis-data.py tmp/slug_github.md
    python3.12 scripts/extract-repo-analysis-data.py tmp/slug_github.md --key related_repositories.recommended_for_deep_analysis
    python3.12 scripts/extract-repo-analysis-data.py tmp/slug_github.md --key web_search_keywords --format prompt

出力:
    JSON（デフォルト）またはプロンプト用テキスト（--format prompt）

依存: python3.12, pyyaml (PyYAML未インストール時は簡易パーサーにフォールバック)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ─── YAML簡易パーサー（PyYAML不要） ─────────────────────────────

def _parse_yaml_simple(text: str) -> dict:
    """
    簡易YAMLパーサー。
    対応: スカラー値、リスト、ネストされたマップ（3階層まで）。
    PyYAMLが利用可能な場合はそちらを優先する。
    """
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        pass

    # フォールバック: 簡易パーサー（3階層対応）
    result: dict = {}
    # stack: (container, indent_level)
    # container は dict または list
    stack: list[tuple[dict | list, int]] = [(result, -1)]
    # 最後にリストに追加されたマップアイテムを追跡
    last_list_item: dict | None = None
    last_list_item_indent: int = -1

    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        content_part = stripped.lstrip()

        # リストアイテムの継続行（インデントが深い key: value）
        if last_list_item is not None and indent > last_list_item_indent and not content_part.startswith("- "):
            if ":" in content_part:
                k, _, v = content_part.partition(":")
                last_list_item[k.strip()] = _parse_value(v.strip())
                continue

        # リストアイテム
        if content_part.startswith("- "):
            item_text = content_part[2:].strip()

            # 親コンテナを特定（スタックを巻き戻し）
            while len(stack) > 1 and indent <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0]

            # 親がdictの場合、最後のキーの値をリストにする
            if isinstance(parent, dict):
                last_key = list(parent.keys())[-1] if parent else None
                if last_key is not None:
                    if not isinstance(parent[last_key], list):
                        parent[last_key] = []
                    target_list = parent[last_key]
                else:
                    continue
            elif isinstance(parent, list):
                target_list = parent
            else:
                continue

            if ":" in item_text:
                # リスト内マップの最初のキー
                map_item: dict = {}
                k, _, v = item_text.partition(":")
                map_item[k.strip()] = _parse_value(v.strip())
                target_list.append(map_item)
                last_list_item = map_item
                last_list_item_indent = indent
            else:
                target_list.append(_parse_value(item_text))
                last_list_item = None
                last_list_item_indent = -1

        # キー: 値（トップレベルまたはネスト）
        elif ":" in content_part:
            last_list_item = None
            last_list_item_indent = -1

            # スタックを巻き戻し
            while len(stack) > 1 and indent <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0]

            if isinstance(parent, dict):
                key, _, value = content_part.partition(":")
                key = key.strip()
                value = value.strip()
                if value:
                    parent[key] = _parse_value(value)
                else:
                    parent[key] = {}
                    stack.append((parent[key], indent))

    return result


def _parse_value(value: str):
    """YAML値をPythonオブジェクトに変換。"""
    if not value:
        return None
    # null
    if value in ("null", "~", "None"):
        return None
    # boolean
    if value in ("true", "True", "yes"):
        return True
    if value in ("false", "False", "no"):
        return False
    # number
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    # list (inline)
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].split(",")
        return [_parse_value(item.strip().strip("\"'")) for item in items if item.strip()]
    # string (remove quotes)
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


# ─── メイン処理 ──────────────────────────────────────────────────

START_MARKER = "# --- machine-readable-data ---"
END_MARKER = "# --- end-machine-readable-data ---"


def extract_machine_readable_data(file_path: Path) -> dict:
    """ファイルから機械可読データセクションを抽出してパースする。"""
    content = file_path.read_text(encoding="utf-8")

    # マーカー間のYAMLを抽出
    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print(f"エラー: 機械可読データセクションが見つかりません: {file_path}", file=sys.stderr)
        sys.exit(1)

    yaml_text = content[start_idx + len(START_MARKER):end_idx].strip()

    # マーカーがコードブロック内に書かれている場合のフォールバック除去
    # （正しい出力ではコードブロック外に書かれるが、念のため対応）
    yaml_text = re.sub(r"^```yaml\s*\n?", "", yaml_text)
    yaml_text = re.sub(r"\n?```\s*$", "", yaml_text)

    return _parse_yaml_simple(yaml_text)


def get_nested_value(data: dict, key_path: str):
    """ドット区切りのキーパスでネストされた値を取得する。"""
    keys = key_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def format_as_prompt(data, key_path: str) -> str:
    """データをプロンプト埋め込み用のテキストに変換する。"""
    if isinstance(data, list):
        return "\n".join(f"- {json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else item}" for item in data)
    elif isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}: {', '.join(str(i) for i in v)}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    else:
        return str(data)


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: python3.12 scripts/extract-repo-analysis-data.py <input_file> [--key <path>] [--format json|prompt]", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1]).expanduser()
    key_path: str | None = None
    output_format = "json"

    # 引数解析
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--key" and i + 1 < len(args):
            key_path = args[i + 1]
            i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        else:
            i += 1

    if not file_path.exists():
        print(f"エラー: ファイルが見つかりません: {file_path}", file=sys.stderr)
        sys.exit(1)

    data = extract_machine_readable_data(file_path)

    # キーパス指定がある場合はネストされた値を取得
    if key_path:
        data = get_nested_value(data, key_path)
        if data is None:
            print(f"エラー: キー '{key_path}' が見つかりません", file=sys.stderr)
            sys.exit(1)

    # 出力
    if output_format == "prompt":
        print(format_as_prompt(data, key_path or ""))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
