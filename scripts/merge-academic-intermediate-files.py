#!/usr/bin/env python3.12
"""
merge-academic-intermediate-files: 分野別中間ファイルを統合レポートにマージ

目的:
    各分野のextractorが生成した中間ファイル（Markdown）を
    1つの統合レポートに結合する。

使い方:
    python3.12 scripts/merge-academic-intermediate-files.py --input file1.md,file2.md --output report.md --date 2026-05-11

出力: 統合されたアカデミックトレンドレポート
依存: python3.12
"""

import argparse
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

# 分野の表示順序
FIELD_ORDER = [
    "ml_ai",
    "cv_robotics",
    "se_it",
    "economics",
    "behavioral_biz",
    "interdisciplinary",
]

FIELD_DISPLAY_NAMES = {
    "ml_ai": "機械学習・AI",
    "cv_robotics": "コンピュータビジョン・ロボティクス",
    "se_it": "IT・情報科学",
    "economics": "経済学",
    "behavioral_biz": "行動心理学・経済心理学・ビジネス",
    "interdisciplinary": "学際・応用・IoT",
}


# ─── マージ処理 ──────────────────────────────────────────────────

def merge_files(input_paths: list[Path], output_path: Path, date: str) -> bool:
    """中間ファイルを統合レポートにマージする。"""
    # 各ファイルの内容を読み込み
    contents: dict[str, str] = {}
    sources: set[str] = set()

    for path in input_paths:
        if not path.exists():
            print(f"  ⚠️  ファイルなし: {path}", file=sys.stderr)
            continue

        content = path.read_text(encoding="utf-8")
        field_name = path.stem.replace("_intermediate", "")
        contents[field_name] = content

        # ソース抽出（中間ファイルのヘッダーから）
        for line in content.splitlines():
            if line.startswith("sources:"):
                src_str = line.split(":", 1)[1].strip().strip("[]")
                for s in src_str.split(","):
                    s = s.strip()
                    if s:
                        sources.add(s)

    if not contents:
        print("⚠️  有効な中間ファイルなし", file=sys.stderr)
        return False

    # ソースリスト構築
    source_list = sorted(sources) if sources else ["arXiv", "NBER", "web_search"]

    # 統合レポート生成
    lines = [
        "---",
        f"date: {date}",
        "collected_by: academic-trend-scout",
        f"sources: [{', '.join(source_list)}]",
        "---",
        f"# アカデミックトレンドレポート: {date}",
        "",
    ]

    # 各分野の内容を順序通りに結合
    for field in FIELD_ORDER:
        if field in contents:
            # 中間ファイルのfrontmatterを除去して本文のみ追加
            field_content = _strip_frontmatter(contents[field])
            if field_content.strip():
                lines.append(field_content)
                lines.append("")

    # 出力
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 統合レポート生成: {output_path}")
    return True


def _strip_frontmatter(content: str) -> str:
    """Markdownのfrontmatter（---で囲まれた部分）を除去する。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content

    # 2つ目の---を探す
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:]).strip()

    return content


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="アカデミック中間ファイル統合")
    parser.add_argument("--input", required=True,
                        help="中間ファイルパス（カンマ区切り）")
    parser.add_argument("--output", required=True, help="出力ファイルパス")
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    args = parser.parse_args()

    input_paths = [Path(p.strip()) for p in args.input.split(",") if p.strip()]
    output_path = Path(args.output)

    print(f"📂 中間ファイル統合（対象日: {args.date}）")
    print(f"   入力: {len(input_paths)}ファイル")
    print(f"   出力: {output_path}")

    success = merge_files(input_paths, output_path, args.date)
    if not success:
        sys.exit(1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
