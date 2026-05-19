#!/usr/bin/env python3.12
"""
extract-gws-slides-text: Google Slides APIのJSONレスポンスからテキストを抽出する

目的:
    gws slides presentations get の出力（JSON）からテキスト内容のみを抽出し、
    指定バイト数で切り詰めて出力する。
    エージェントのコンテキストウィンドウ消費を抑制するために使用する。

使い方:
    gws slides presentations get --params '{"presentationId": "ID"}' | python3.12 ~/scripts/extract-gws-slides-text.py
    python3.12 ~/scripts/extract-gws-slides-text.py < raw_slides.json
    python3.12 ~/scripts/extract-gws-slides-text.py --max-bytes 5000 < raw_slides.json
    python3.12 ~/scripts/extract-gws-slides-text.py --input raw_slides.json

出力: 抽出されたテキスト（UTF-8、指定バイト数以内）
依存: python3.12（標準ライブラリのみ）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
from typing import Any

# ─── 定数 ────────────────────────────────────────────────────────

DEFAULT_MAX_BYTES = 8000


# ─── テキスト抽出 ────────────────────────────────────────────────

def extract_text_from_presentation(doc: dict[str, Any]) -> str:
    """Google Slides APIのレスポンスからテキストを抽出する。"""
    parts: list[str] = []
    slides = doc.get("slides", [])

    for idx, slide in enumerate(slides, 1):
        slide_parts: list[str] = []
        for element in slide.get("pageElements", []):
            _extract_page_element(element, slide_parts)

        if slide_parts:
            parts.append(f"--- Slide {idx} ---\n")
            parts.extend(slide_parts)
            parts.append("\n")

    return "".join(parts)


def _extract_page_element(element: dict[str, Any], parts: list[str]) -> None:
    """ページ要素からテキストを抽出する。"""
    if "shape" in element:
        _extract_shape(element["shape"], parts)
    elif "table" in element:
        _extract_table(element["table"], parts)
    elif "elementGroup" in element:
        for child in element["elementGroup"].get("children", []):
            _extract_page_element(child, parts)


def _extract_shape(shape: dict[str, Any], parts: list[str]) -> None:
    """シェイプからテキストを抽出する。"""
    text_content = shape.get("text", {})
    for text_element in text_content.get("textElements", []):
        if "textRun" in text_element:
            content = text_element["textRun"].get("content", "")
            parts.append(content)


def _extract_table(table: dict[str, Any], parts: list[str]) -> None:
    """テーブルからテキストを抽出する。"""
    for row in table.get("tableRows", []):
        for cell in row.get("tableCells", []):
            text_content = cell.get("text", {})
            for text_element in text_content.get("textElements", []):
                if "textRun" in text_element:
                    content = text_element["textRun"].get("content", "")
                    parts.append(content)


# ─── バイト数制限 ────────────────────────────────────────────────

def truncate_to_bytes(text: str, max_bytes: int) -> str:
    """UTF-8でmax_bytesを超えないように切り詰める。"""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    suffix = "\n...[truncated]"
    suffix_bytes = len(suffix.encode("utf-8"))
    target_bytes = max_bytes - suffix_bytes

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
    text = extract_text_from_presentation(doc)

    # 出力組み立て
    output = f"# {title}\n\n{text}"

    # バイト数制限
    output = truncate_to_bytes(output, max_bytes)

    print(output)



if __name__ == "__main__":
    main()
