#!/usr/bin/env python3.12
"""
summarize-filtered-metadata: フィルタ済みメタデータをextractor向けに軽量化する

目的:
    filter-gws-drive-metadata.py の出力（全件含む大きなJSON）から、
    extractorエージェントが読み込む軽量版JSONを生成する。
    低関連度ドキュメントは件数・カテゴリ別集計のみに圧縮し、
    コンテキストウィンドウの逼迫を防止する。

使い方:
    python3.12 scripts/summarize-filtered-metadata.py \
        --input tmp/sheets_filtered.json \
        --output tmp/sheets_for_extractor.json \
        --top 10

入力: filter-gws-drive-metadata.py の --output で生成されたJSON
出力: extractorが readFile で読み込む軽量JSON

依存: python3.12（標準ライブラリのみ）
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

# ─── カテゴリ推定用パターン ──────────────────────────────────────

CATEGORY_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    ("日報・報告", [
        re.compile(r"日報", re.IGNORECASE),
        re.compile(r"報告", re.IGNORECASE),
        re.compile(r"進捗", re.IGNORECASE),
    ]),
    ("顧客管理", [
        re.compile(r"顧客", re.IGNORECASE),
        re.compile(r"ヒアリング", re.IGNORECASE),
        re.compile(r"顧客情報確認", re.IGNORECASE),
    ]),
    ("営業・商談", [
        re.compile(r"商談", re.IGNORECASE),
        re.compile(r"架電", re.IGNORECASE),
        re.compile(r"トークスクリプト", re.IGNORECASE),
        re.compile(r"失注", re.IGNORECASE),
    ]),
    ("審査・契約", [
        re.compile(r"審査", re.IGNORECASE),
        re.compile(r"契約", re.IGNORECASE),
        re.compile(r"承認", re.IGNORECASE),
        re.compile(r"不備コード", re.IGNORECASE),
    ]),
    ("物流・車両", [
        re.compile(r"ロジコ", re.IGNORECASE),
        re.compile(r"車両", re.IGNORECASE),
        re.compile(r"カートレ", re.IGNORECASE),
        re.compile(r"解体", re.IGNORECASE),
        re.compile(r"搬入", re.IGNORECASE),
    ]),
    ("データ・分析", [
        re.compile(r"KPI", re.IGNORECASE),
        re.compile(r"集計", re.IGNORECASE),
        re.compile(r"レポート", re.IGNORECASE),
        re.compile(r"分析", re.IGNORECASE),
        re.compile(r"CDATA", re.IGNORECASE),
    ]),
    ("保険", [
        re.compile(r"保険", re.IGNORECASE),
        re.compile(r"ヒアリングシート", re.IGNORECASE),
    ]),
    ("督促・未収", [
        re.compile(r"督促", re.IGNORECASE),
        re.compile(r"未収", re.IGNORECASE),
    ]),
    ("マーケティング", [
        re.compile(r"LP", re.IGNORECASE),
        re.compile(r"クリエイティブ", re.IGNORECASE),
        re.compile(r"広告", re.IGNORECASE),
        re.compile(r"キャンペーン", re.IGNORECASE),
    ]),
]


def categorize(name: str) -> str:
    """ファイル名からカテゴリを推定する。"""
    for category, patterns in CATEGORY_PATTERNS:
        for pattern in patterns:
            if pattern.search(name):
                return category
    return "その他"


def main() -> None:
    args = sys.argv[1:]
    input_file: str | None = None
    output_file: str | None = None
    top_count: int = 10

    i = 0
    while i < len(args):
        if args[i] == "--input":
            i += 1
            input_file = args[i]
        elif args[i] == "--output":
            i += 1
            output_file = args[i]
        elif args[i] == "--top":
            i += 1
            top_count = int(args[i])
        elif args[i] in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{args[i]}'", file=sys.stderr)
            sys.exit(1)
        i += 1

    if not input_file or not output_file:
        print("Error: --input and --output are required", file=sys.stderr)
        sys.exit(1)

    # 入力読み込み
    try:
        with open(input_file, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    summary = data.get("summary", {})
    top_files = data.get("top_files", [])
    all_files = data.get("all_files", [])

    # top_files は指定件数に制限（通常はフィルタスクリプトで既に制限済み）
    top_files = top_files[:top_count]
    top_ids = {f.get("id") for f in top_files}

    # 低関連度（top_files以外）のカテゴリ集計
    low_relevance_files = [f for f in all_files if f.get("id") not in top_ids]
    category_counts: dict[str, int] = {}
    for f in low_relevance_files:
        cat = categorize(f.get("name", ""))
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 軽量版出力
    result: dict[str, Any] = {
        "summary": summary,
        "top_files": top_files,
        "low_relevance_summary": {
            "count": len(low_relevance_files),
            "categories": category_counts,
        },
    }

    # 出力
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(
        f"✅ 軽量化完了: {len(top_files)}件(top) + "
        f"{len(low_relevance_files)}件(集計のみ) → {output_path}"
    )


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
