#!/usr/bin/env python3.12
"""
extract-gws-doc-text: Google Docs APIのJSONレスポンスからテキストを抽出する

目的:
    gws docs documents get の出力（JSON）からテキスト内容のみを抽出し、
    指定バイト数で切り詰めて出力する。
    エージェントのコンテキストウィンドウ消費を抑制するために使用する。

使い方:
    gws docs documents get --params '{"documentId": "ID"}' | python3.12 ~/scripts/extract-gws-doc-text.py
    python3.12 ~/scripts/extract-gws-doc-text.py < raw_doc.json
    python3.12 ~/scripts/extract-gws-doc-text.py --max-bytes 5000 < raw_doc.json
    python3.12 ~/scripts/extract-gws-doc-text.py --input raw_doc.json
    python3.12 ~/scripts/extract-gws-doc-text.py --input raw_doc.json --max-bytes 10000

出力: 抽出されたテキスト（UTF-8、指定バイト数以内）
依存: python3.12（標準ライブラリのみ）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
from typing import Any

# ─── 定数 ────────────────────────────────────────────────────────

DEFAULT_MAX_BYTES = 8000


# ─── テキスト抽出 ────────────────────────────────────────────────

def extract_text_from_body(body: dict[str, Any]) -> str:
    """Google Docs APIのbodyからテキストを抽出する。

    対応する構造要素:
    - paragraph (通常テキスト、見出し)
    - table (テーブル内テキスト)
    - tableOfContents (目次)
    - sectionBreak (無視)
    """
    parts: list[str] = []

    for element in body.get("content", []):
        _extract_structural_element(element, parts)

    return "".join(parts)


def _extract_structural_element(element: dict[str, Any], parts: list[str]) -> None:
    """構造要素からテキストを再帰的に抽出する。"""
    if "paragraph" in element:
        _extract_paragraph(element["paragraph"], parts)
    elif "table" in element:
        _extract_table(element["table"], parts)
    elif "tableOfContents" in element:
        _extract_table_of_contents(element["tableOfContents"], parts)


def _extract_paragraph(paragraph: dict[str, Any], parts: list[str]) -> None:
    """パラグラフからテキストを抽出する。"""
    for elem in paragraph.get("elements", []):
        if "textRun" in elem:
            content = elem["textRun"].get("content", "")
            parts.append(content)
        elif "inlineObjectElement" in elem:
            parts.append("[画像]")


def _extract_table(table: dict[str, Any], parts: list[str]) -> None:
    """テーブルからテキストを抽出する。"""
    for row in table.get("tableRows", []):
        for cell in row.get("tableCells", []):
            for element in cell.get("content", []):
                _extract_structural_element(element, parts)


def _extract_table_of_contents(toc: dict[str, Any], parts: list[str]) -> None:
    """目次からテキストを抽出する。"""
    for element in toc.get("content", []):
        _extract_structural_element(element, parts)


# ─── バイト数制限 ────────────────────────────────────────────────

def truncate_to_bytes(text: str, max_bytes: int) -> str:
    """UTF-8でmax_bytesを超えないように切り詰める。

    文字の途中で切れないよう、文字単位で切り詰める。
    切り詰めた場合は末尾に「...[truncated]」を付与する。
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    suffix = "\n...[truncated]"
    suffix_bytes = len(suffix.encode("utf-8"))
    target_bytes = max_bytes - suffix_bytes

    # 文字単位で切り詰め
    truncated = encoded[:target_bytes].decode("utf-8", errors="ignore")
    return truncated + suffix


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    max_bytes = DEFAULT_MAX_BYTES
    input_file: str | None = None

    i = 0
    while i < len(args):
        if args[i] == "--max-bytes":
            i += 1
            if i >= len(args):
                print("Error: --max-bytes requires a number", file=sys.stderr)
                sys.exit(1)
            max_bytes = int(args[i])
        elif args[i] == "--input":
            i += 1
            if i >= len(args):
                print("Error: --input requires a file path", file=sys.stderr)
                sys.exit(1)
            input_file = args[i]
        elif args[i] in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{args[i]}'", file=sys.stderr)
            sys.exit(1)
        i += 1

    # JSON読み込み
    try:
        if input_file:
            with open(input_file, encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # エラーレスポンスのチェック
    if "error" in doc:
        error = doc["error"]
        msg = error.get("message", "unknown error")
        print(f"Error: API returned error: {msg}", file=sys.stderr)
        sys.exit(1)

    # テキスト抽出
    title = doc.get("title", "(untitled)")
    body = doc.get("body", {})
    text = extract_text_from_body(body)

    # 出力組み立て
    output = f"# {title}\n\n{text}"

    # バイト数制限
    output = truncate_to_bytes(output, max_bytes)

    print(output)



if __name__ == "__main__":
    main()
