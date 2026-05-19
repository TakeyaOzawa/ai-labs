#!/usr/bin/env python3.12
"""
merge-gws-intermediate-files: GWSトレンド中間ファイルを統合レポートに結合する

目的:
    gws-trend-extractorが生成した中間ファイル（docs.md, slides.md等）を
    統合レポートの骨格として結合する。
    markdown-reporterのコンテキスト逼迫を防止するため、
    転記部分をPythonスクリプトで処理し、reporterには分析部分のみを担当させる。

使い方:
    python3.12 scripts/merge-gws-intermediate-files.py \
        --input tmp/docs.md,tmp/slides.md,tmp/sheets.md,tmp/pdf.md \
        --output scout_reports/gws_trends/daily/2026-05-11_gws_daily.md \
        --date 2026-05-11

出力: 統合レポート（サマリーテーブル + 種別セクション転記済み）
      分析用サマリーファイル（reporterが読む軽量版）

依存: python3.12（標準ライブラリのみ）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
import re
from typing import Any

# ─── 種別マッピング ──────────────────────────────────────────────

TYPE_DISPLAY = {
    "docs": ("📄", "Google Docs"),
    "slides": ("📊", "Google Slides"),
    "sheets": ("📈", "Google Sheets"),
    "forms": ("📝", "Google Forms"),
    "pdf": ("📎", "PDF"),
}


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Markdownのフロントマターを解析する。"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    meta: dict[str, str] = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = parts[2].strip()
    return meta, body


def extract_high_relevance_docs(body: str) -> list[dict[str, str]]:
    """高関連度セクションからドキュメント情報を抽出する。"""
    docs: list[dict[str, str]] = []
    in_high = False
    current_doc: dict[str, str] = {}

    for line in body.split("\n"):
        if "⭐⭐⭐ 高関連度" in line:
            in_high = True
            continue
        if in_high and ("⭐⭐ 中関連度" in line or "⭐ 低関連度" in line):
            if current_doc:
                docs.append(current_doc)
            break
        if in_high:
            if line.startswith("### "):
                if current_doc:
                    docs.append(current_doc)
                current_doc = {"name": line[4:].strip()}
            elif line.startswith("- **カテゴリ**:"):
                current_doc["category"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **オーナー**:"):
                current_doc["owner"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **概要**:"):
                current_doc["summary"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **リンク**:"):
                current_doc["link"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **ネクストアクション**:"):
                current_doc["next_action"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **最終更新**:"):
                current_doc["updated"] = line.split(":", 1)[1].strip()

    if current_doc and in_high:
        docs.append(current_doc)

    return docs


def extract_all_docs_with_metadata(body: str) -> list[dict[str, str]]:
    """全セクション（高・中・低）からドキュメント情報を抽出する。"""
    docs: list[dict[str, str]] = []
    current_doc: dict[str, str] = {}
    current_relevance = ""

    for line in body.split("\n"):
        if "⭐⭐⭐ 高関連度" in line:
            current_relevance = "⭐⭐⭐"
            continue
        elif "⭐⭐ 中関連度" in line:
            if current_doc:
                docs.append(current_doc)
                current_doc = {}
            current_relevance = "⭐⭐"
            continue
        elif "⭐ 低関連度" in line:
            if current_doc:
                docs.append(current_doc)
                current_doc = {}
            current_relevance = "⭐"
            continue

        if current_relevance in ("⭐⭐⭐", "⭐⭐"):
            if line.startswith("### "):
                if current_doc:
                    docs.append(current_doc)
                current_doc = {"name": line[4:].strip(), "relevance": current_relevance}
            elif line.startswith("- **カテゴリ**:"):
                current_doc["category"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **オーナー**:"):
                current_doc["owner"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **最終更新者**:"):
                current_doc["last_editor"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **最終更新**:"):
                current_doc["updated"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **リンク**:"):
                current_doc["link"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **ネクストアクション**:"):
                current_doc["next_action"] = line.split(":", 1)[1].strip()

    if current_doc:
        docs.append(current_doc)

    return docs


def adjust_heading_level(body: str) -> str:
    """見出しレベルを1段下げる（## → ###, ### → ####）。"""
    lines = []
    for line in body.split("\n"):
        if line.startswith("## "):
            lines.append("###" + line[2:])
        elif line.startswith("### "):
            lines.append("####" + line[3:])
        else:
            lines.append(line)
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    input_files_str: str = ""
    output_file: str = ""
    base_date: str = ""

    i = 0
    while i < len(args):
        if args[i] == "--input":
            i += 1
            input_files_str = args[i]
        elif args[i] == "--output":
            i += 1
            output_file = args[i]
        elif args[i] == "--date":
            i += 1
            base_date = args[i]
        elif args[i] in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{args[i]}'", file=sys.stderr)
            sys.exit(1)
        i += 1

    if not input_files_str or not output_file or not base_date:
        print("Error: --input, --output, --date are required", file=sys.stderr)
        sys.exit(1)

    input_paths = [Path(p.strip()) for p in input_files_str.split(",")]

    # 中間ファイル読み込み
    type_data: dict[str, tuple[dict[str, str], str]] = {}
    for path in input_paths:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)
        type_name = meta.get("type", path.stem)
        type_data[type_name] = (meta, body)

    if not type_data:
        print("Error: no valid intermediate files found", file=sys.stderr)
        sys.exit(1)

    # サマリーテーブル構築
    summary_rows: list[str] = []
    all_high_docs: list[dict[str, str]] = []
    all_docs: list[dict[str, str]] = []  # 全種別の高・中関連度ドキュメント

    for type_name in ["docs", "slides", "sheets", "forms", "pdf"]:
        if type_name not in type_data:
            continue
        meta, body = type_data[type_name]
        icon, display_name = TYPE_DISPLAY.get(type_name, ("📁", type_name))
        total = meta.get("total_count", "0")
        filtered = meta.get("filtered_count", "0")
        high = meta.get("high_count", "0")
        mid = meta.get("mid_count", "0")
        low = meta.get("low_count", "0")
        summary_rows.append(
            f"| {icon} {display_name} | {total}件 | {filtered}件 | {high}件 | {mid}件 | {low}件 |"
        )

        # 高関連度ドキュメント抽出
        high_docs = extract_high_relevance_docs(body)
        for doc in high_docs:
            doc["type"] = type_name
            doc["type_icon"] = icon
        all_high_docs.extend(high_docs)

        # 全ドキュメント（高・中）抽出
        type_docs = extract_all_docs_with_metadata(body)
        for doc in type_docs:
            doc["type"] = type_name
            doc["type_icon"] = icon
            doc["type_display"] = display_name
        all_docs.extend(type_docs)

    # 統合レポート構築
    output_lines: list[str] = []

    # フロントマター
    output_lines.append("---")
    output_lines.append(f"date: {base_date}")
    output_lines.append(f"period: {base_date} 〜 {base_date}")
    output_lines.append("collected_by: gws-trend-scout")
    output_lines.append("document_types:")
    for type_name in ["docs", "slides", "sheets", "forms", "pdf"]:
        if type_name in type_data:
            _, display_name = TYPE_DISPLAY.get(type_name, ("", type_name))
            output_lines.append(f"  - {display_name}")
    output_lines.append("---")
    output_lines.append("")

    # タイトル
    output_lines.append(f"# GWS日次トレンド: {base_date}")
    output_lines.append(f"**対象期間**: {base_date} 〜 {base_date}")
    output_lines.append("")

    # サマリーテーブル
    output_lines.append("## 📊 サマリー")
    output_lines.append("")
    output_lines.append("| 種別 | 取得件数 | フィルタ後 | 高関連度 | 中関連度 | 低関連度 |")
    output_lines.append("| --- | --- | --- | --- | --- | --- |")
    output_lines.extend(summary_rows)
    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

    # 注目ドキュメント（Top 5）— 高関連度から最大5件
    output_lines.append("## 🔥 注目ドキュメント（Top 5）")
    output_lines.append("")
    for i, doc in enumerate(all_high_docs[:5], 1):
        output_lines.append(f"### {i}. {doc.get('name', '不明')}")
        output_lines.append("")
        output_lines.append(f"- **種別**: {doc.get('type_icon', '')} {TYPE_DISPLAY.get(doc.get('type', ''), ('', ''))[1]}")
        if doc.get("category"):
            output_lines.append(f"- **カテゴリ**: {doc['category']}")
        if doc.get("owner"):
            output_lines.append(f"- **オーナー**: {doc['owner']}")
        if doc.get("summary"):
            output_lines.append(f"- **概要**: {doc['summary']}")
        if doc.get("link"):
            output_lines.append(f"- **リンク**: {doc['link']}")
        output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

    # 種別セクション転記
    for type_name in ["docs", "slides", "sheets", "forms", "pdf"]:
        if type_name not in type_data:
            continue
        icon, display_name = TYPE_DISPLAY.get(type_name, ("📁", type_name))
        meta, body = type_data[type_name]
        output_lines.append(f"## {icon} {display_name}")
        output_lines.append("")
        output_lines.append(adjust_heading_level(body))
        output_lines.append("")
        output_lines.append("---")
        output_lines.append("")

    # カテゴリ別クロスリファレンス
    output_lines.append("## 🏷️ カテゴリ別クロスリファレンス")
    output_lines.append("")

    # カテゴリごとにドキュメントをグループ化
    category_groups: dict[str, list[dict[str, str]]] = {}
    for doc in all_docs:
        cat = doc.get("category", "📁 その他")
        if cat not in category_groups:
            category_groups[cat] = []
        category_groups[cat].append(doc)

    for cat, cat_docs in sorted(category_groups.items()):
        output_lines.append(f"### {cat}")
        output_lines.append("")
        output_lines.append("| 種別 | ドキュメント名 | オーナー | 最終更新者 | 更新日 | 関連度 |")
        output_lines.append("| --- | --- | --- | --- | --- | --- |")
        for doc in cat_docs:
            type_icon = doc.get("type_icon", "")
            name = doc.get("name", "不明")
            link = doc.get("link", "")
            # リンクからURLを抽出（[name](url) 形式）
            if link.startswith("["):
                name_display = link
            else:
                name_display = name
            owner = doc.get("owner", "-")
            last_editor = doc.get("last_editor", "-")
            updated = doc.get("updated", "-")
            relevance = doc.get("relevance", "-")
            output_lines.append(
                f"| {type_icon} | {name_display} | {owner} | {last_editor} | {updated} | {relevance} |"
            )
        output_lines.append("")

    output_lines.append("---")
    output_lines.append("")

    # 前日のトレンド分析
    output_lines.append("## 📈 前日のトレンド")
    output_lines.append("")

    # 最も更新が活発だった種別
    most_active_type = ""
    most_active_count = 0
    total_new = 0
    for type_name in ["docs", "slides", "sheets", "forms", "pdf"]:
        if type_name not in type_data:
            continue
        meta, _ = type_data[type_name]
        filtered = int(meta.get("filtered_count", "0"))
        if filtered > most_active_count:
            most_active_count = filtered
            most_active_type = type_name
        total_new += int(meta.get("total_count", "0"))

    if most_active_type:
        icon, display_name = TYPE_DISPLAY.get(most_active_type, ("", ""))
        output_lines.append(f"- **最も更新が活発だった種別**: {icon} {display_name}（{most_active_count}件）")

    # 最も多くのドキュメントを共有した人
    owner_counts: dict[str, int] = {}
    for doc in all_docs:
        owner = doc.get("owner", "")
        if owner and owner != "-":
            # 括弧内の部署情報を除去して名前だけカウント
            owner_name = owner.split("（")[0].strip()
            owner_counts[owner_name] = owner_counts.get(owner_name, 0) + 1
    if owner_counts:
        top_owner = max(owner_counts, key=owner_counts.get)  # type: ignore[arg-type]
        output_lines.append(f"- **最も多くのドキュメントを共有した人**: {top_owner}（{owner_counts[top_owner]}件）")

    # 新規作成が多かったカテゴリ
    if category_groups:
        top_category = max(category_groups, key=lambda k: len(category_groups[k]))
        output_lines.append(f"- **最も多かったカテゴリ**: {top_category}（{len(category_groups[top_category])}件）")

    output_lines.append(f"- **ドキュメント総数**: {total_new}件")
    output_lines.append(f"- **高・中関連度ドキュメント数**: {len(all_docs)}件")
    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

    # 横断アクションアイテム
    output_lines.append("## 💡 横断アクションアイテム")
    output_lines.append("")
    output_lines.append("| 優先度 | 種別 | ドキュメント | アクション | 期限・予定 |")
    output_lines.append("| --- | --- | --- | --- | --- |")

    # 高関連度 → 🔴高、中関連度 → 🟡中
    for doc in all_docs:
        next_action = doc.get("next_action", "")
        if not next_action or next_action == "-":
            continue
        relevance = doc.get("relevance", "")
        if "⭐⭐⭐" in relevance:
            priority = "🔴 高"
        else:
            priority = "🟡 中"
        type_icon = doc.get("type_icon", "")
        name = doc.get("name", "不明")
        link = doc.get("link", "")
        if link.startswith("["):
            name_display = link
        else:
            name_display = name
        output_lines.append(
            f"| {priority} | {type_icon} | {name_display} | {next_action} | - |"
        )

    output_lines.append("")

    # ファイル出力
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines), encoding="utf-8")

    print(f"✅ 統合レポート生成完了")
    print(f"- 出力: {output_path}")
    print(f"- 入力ファイル数: {len(type_data)}/{len(input_paths)}")
    print(f"- 注目ドキュメント: {min(len(all_high_docs), 5)}件")



if __name__ == "__main__":
    main()
