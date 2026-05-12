#!/usr/bin/env python3.12
"""
split-academic-feeds: アカデミックフィードを分野別に分割する

目的:
    academic-trend-scoutのフィードファイル（.tmp_{date}_feeds.md）を
    分野別の小さなファイルに分割し、各extractorが独立して処理できるようにする。
    各分野のフィードサイズを制限し、コンテキスト逼迫を防ぐ。

使い方:
    python3.12 scripts/split-academic-feeds.py --date 2026-05-11 [--max-items 100]

出力: Documents/works/scout_histories/academic_trends/daily/tmp/{field}_feed.md
依存: python3.12
"""

import argparse
import re
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

HOME = Path.home()
FEED_DIR = HOME / "Documents" / "works" / "scout_histories" / "academic_trends" / "daily"
TMP_DIR = FEED_DIR / "tmp"

# 分野定義: 分野名 → フィードセクション名のリスト
FIELD_MAPPING: dict[str, list[str]] = {
    "ml_ai": [
        "arXiv cs.AI",
        "arXiv cs.LG (Machine Learning)",
        "Hugging Face Papers",
    ],
    "cv_robotics": [
        "arXiv cs.CV (Computer Vision)",
        "arXiv cs.RO (Robotics/Drones)",
    ],
    "se_it": [
        "arXiv cs.SE (Software Engineering)",
    ],
    "economics": [
        "arXiv econ.GN (General Economics)",
        "NBER New Working Papers",
    ],
}

# Web検索のみの分野（フィードなし）
WEB_ONLY_FIELDS = ["behavioral_biz", "interdisciplinary"]

DEFAULT_MAX_ITEMS = 80  # 分野あたりの最大記事数


# ─── パース ──────────────────────────────────────────────────────

def parse_feed_sections(content: str) -> dict[str, list[str]]:
    """フィードファイルをセクション名 → 記事リストに分解する。"""
    sections: dict[str, list[str]] = {}
    current_section = ""
    current_items: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = line[3:].strip()
            current_items = []
        elif line.startswith("- ["):
            current_items.append(line)
        elif current_items and line.startswith("  - "):
            # summary行: 直前の記事に付属
            current_items[-1] += "\n" + line

    # 最後のセクション
    if current_section and current_items:
        sections[current_section] = current_items

    return sections


def split_feeds(
    feed_path: Path,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> dict[str, Path]:
    """フィードファイルを分野別に分割する。

    Returns:
        分野名 → 出力ファイルパスのマッピング
    """
    if not feed_path.exists():
        print(f"⚠️  フィードファイルが見つかりません: {feed_path}", file=sys.stderr)
        return {}

    content = feed_path.read_text(encoding="utf-8")
    sections = parse_feed_sections(content)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}

    for field_name, section_names in FIELD_MAPPING.items():
        items: list[str] = []
        source_sections: list[str] = []

        for section_name in section_names:
            section_items = sections.get(section_name, [])
            if section_items:
                source_sections.append(section_name)
                items.extend(section_items)

        if not items:
            print(f"  ⏭️  {field_name}: 記事なし（スキップ）")
            continue

        # 件数制限（先頭から取得）
        original_count = len(items)
        if len(items) > max_items:
            items = items[:max_items]

        # 出力
        output_path = TMP_DIR / f"{field_name}_feed.md"
        lines = [
            f"# {field_name} フィード（{len(items)}件 / 元{original_count}件）\n",
            f"ソース: {', '.join(source_sections)}\n",
            "",
        ]
        for item in items:
            lines.append(item)

        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output_paths[field_name] = output_path
        print(f"  ✅ {field_name}: {len(items)}件（元{original_count}件）→ {output_path}")

    return output_paths


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="アカデミックフィード分野別分割")
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS,
                        help=f"分野あたりの最大記事数（デフォルト: {DEFAULT_MAX_ITEMS}）")
    args = parser.parse_args()

    feed_path = FEED_DIR / f".tmp_{args.date}_feeds.md"
    print(f"📂 フィード分割開始（対象日: {args.date}）")
    print(f"   入力: {feed_path}")
    print(f"   最大件数/分野: {args.max_items}")

    output_paths = split_feeds(feed_path, max_items=args.max_items)

    if output_paths:
        print(f"\n✅ 完了: {len(output_paths)}分野に分割")
    else:
        print("\n⚠️  分割対象なし")
        sys.exit(1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
