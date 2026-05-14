#!/usr/bin/env python3.12
"""CSVからコンタクト履歴テーブル定義に合致するカラムのみ抽出する."""
import csv
import sys
from datetime import datetime
from pathlib import Path

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <input.csv>", file=sys.stderr)
    sys.exit(1)

INPUT = Path(sys.argv[1])
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
OUTPUT = INPUT.with_name(f"コンタクト履歴_{timestamp}.csv")

KEEP_COLUMNS = [
    "レコード番号", "更新者", "作成者", "更新日時", "作成日時",
    "顧客一覧レコード番号", "姓", "名", "通信欄",
    "フラグ[電話]", "フラグ[不在]", "フラグ[メール]", "フラグ[SMS]",
    "フラグ[LINE]", "フラグ[書類送付]", "フラグ[OAC回付]",
    "ヨミ", "ネクストアクション", "予定日", "タスク", "対応者",
    "タスク担当者", "進捗管理", "中古進捗管理", "その他", "顧客ID",
    "(新車)検討ポイント", "(中古)検討ポイント",
    "失注_大のカテゴリー", "失注_中のカテゴリー", "失注_小のカテゴリー",
    "失注理由その他＿自由記載", "スタンス", "継続商談理由", "期日",
    "即失注[即失注]", "架電不在日", "アポ結果[不在]", "初回商談時テンプレ",
]

with INPUT.open(encoding="utf-8-sig") as fin, OUTPUT.open("w", encoding="utf-8-sig", newline="") as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=KEEP_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in reader:
        writer.writerow({col: row.get(col, "") for col in KEEP_COLUMNS})

print(f"完了: {OUTPUT} ({sum(1 for _ in OUTPUT.open(encoding='utf-8-sig')) - 1} 行)")
