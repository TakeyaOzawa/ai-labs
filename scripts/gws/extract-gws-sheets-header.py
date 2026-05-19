#!/usr/bin/env python3.12
"""
extract-gws-sheets-header: Sheets values.get の出力からヘッダー行を抽出する

目的:
    gws sheets spreadsheets values get の JSON 出力を受け取り、
    シート名とヘッダー行（最大5行）をコンパクトなテキストに変換する。
    extractorエージェントのコンテキスト消費を最小限に抑える。

使い方:
    gws sheets spreadsheets values get --params '{"spreadsheetId": "...", "range": "A1:Z5"}' \
        | python3.12 ~/scripts/extract-gws-sheets-header.py

出力例:
    シート: Sheet1
    ヘッダー: 日付 | 担当者 | ステータス | 備考
    行2: 2026-05-01 | 田中 | 完了 | 初回対応
    行3: 2026-05-02 | 佐藤 | 進行中 |
    (全5行)

依存: python3.12（標準ライブラリのみ）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("(JSON解析エラー: シートデータを取得できませんでした)")
        return

    # エラーレスポンスの場合
    if "error" in data:
        error_msg = data["error"].get("message", "不明なエラー")
        print(f"(エラー: {error_msg})")
        return

    # values.get のレスポンス構造
    sheet_range = data.get("range", "不明")
    values = data.get("values", [])

    if not values:
        print(f"シート: {sheet_range}")
        print("(データなし)")
        return

    # シート名を range から抽出（例: "Sheet1!A1:Z5" → "Sheet1"）
    sheet_name = sheet_range.split("!")[0] if "!" in sheet_range else sheet_range

    output_lines = [f"シート: {sheet_name}"]

    for i, row in enumerate(values[:5]):
        # セル値を " | " で結合
        row_text = " | ".join(str(cell) for cell in row if cell)
        if not row_text:
            continue

        if i == 0:
            output_lines.append(f"ヘッダー: {row_text}")
        else:
            output_lines.append(f"行{i + 1}: {row_text}")

    output_lines.append(f"(全{len(values)}行)")

    # 出力を3000文字以内に制限
    result = "\n".join(output_lines)
    if len(result) > 3000:
        result = result[:3000] + "\n...(切り詰め)"

    print(result)



if __name__ == "__main__":
    main()
