#!/usr/bin/env python3.12
"""CSVからテーブル定義に合致するカラムのみ抽出する."""
import csv
import sys
from datetime import datetime
from pathlib import Path

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <input.csv>", file=sys.stderr)
    sys.exit(1)

INPUT = Path(sys.argv[1])
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
OUTPUT = INPUT.with_name(f"顧客一覧_DRM当日更新分_{timestamp}.csv")

KEEP_COLUMNS = [
    "レコード番号", "更新者", "作成者", "更新日時", "作成日時",
    "担当（クロージング担当）", "姓", "名", "姓（カナ）", "名（カナ）",
    "郵便番号", "都道府県", "ヨミ", "初回審査結果日", "初回審査結果",
    "進捗管理", "中古進捗管理", "町名・番地", "性別", "生年月日", "年齢",
    "免許証番号", "初回通電日", "商談意向日", "メール不可[不可]", "会員No", "顧客ID",
    "契約者_電話番号", "契約者_携帯電話番号", "契約者_メールアドレス",
    "契約者_LINE連絡先", "商談希望者_電話番号", "商談希望者_携帯電話番号",
    "商談希望者_メールアドレス", "商談希望者_LINE連絡先",
    "その他_電話番号", "その他_携帯電話番号", "その他_メールアドレス",
    "その他_LINE連絡先", "備考欄", "失注_大のカテゴリー", "失注_中のカテゴリー",
    "失注_小のカテゴリー", "失注理由その他＿自由記載", "新成約ランク",
    "商談設定コンタクト日", "商談予定日", "商談設定者", "アポ結果[不在]",
    "商談予定日（メール配信用）", "商談開始時間", "契約者LINE_ID",
    "商談希望者LINE_ID", "その他LINE_ID", "スタンス", "継続商談理由",
    "期日", "即失注[即失注]", "架電不在日", "返却コメント",
]

with INPUT.open(encoding="utf-8-sig") as fin, OUTPUT.open("w", encoding="utf-8-sig", newline="") as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=KEEP_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in reader:
        writer.writerow({col: row.get(col, "") for col in KEEP_COLUMNS})

print(f"完了: {OUTPUT} ({sum(1 for _ in OUTPUT.open(encoding='utf-8-sig')) - 1} 行)")
