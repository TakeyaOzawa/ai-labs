#!/usr/bin/env python3.12
"""CSV内の個人情報を連番でマスキングする汎用スクリプト.

使い方:
    mask_private_csv.py <input.csv> [<existing_mapping.csv>] [--key COLUMN]

挙動:
- input.csv の各行を読み、MASK_RULES に定義された PII カラムを顧客IDベースの
  安定キー（stable_key）でマスク値に置き換えて出力する。
  顧客IDカラムがない場合は連番をフォールバックとして使用する。
- existing_mapping.csv が指定された場合、同じ一意キーを持つレコードは既存の
  マスク値を再利用する。新規にマスクが発生した分（新規キー、または既存キーで
  新たにマスクされたカラム）のみを差分マッピングとして別ファイルで出力。
- --key は input.csv 側の一意キーカラム名。既定値は「レコード番号」。
- 後続CSV（コンタクト履歴など）では --key で参照カラムを切り替える。
  （例: --key 顧客一覧レコード番号）

マスク対象カラムや生成パターンは MASK_RULES を直接編集する。
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# カラム全体をマスクするルール
# ---------------------------------------------------------------------------
# n = stable_key（顧客IDの4文字目以降を数値化した値）
# SQL側: stable_key = CAST(SUBSTRING(顧客ID, 4) AS UNSIGNED)
# Python側: stable_key = int(顧客ID[3:])  ※顧客IDが "CUS0001" なら stable_key=1
#
# SQL と同一のマスク値を生成するため、以下のルールは SQL の共通マスキング式と
# 完全に対応させている。
MASK_RULES = {
    # --- SQL準拠マスキング ---
    "姓": lambda n: f"かるもーん{n}",
    "名": lambda n: f"検証{n}",
    "姓（カナ）": lambda n: f"カルモーン{n}",
    "名（カナ）": lambda n: f"ケンショウ{n}",
    "免許証番号": lambda n: str(n).zfill(12),
    # 電話番号系: LPAD(stable_key, 11, '0')
    "契約者_電話番号": lambda n: str(n).zfill(11),
    "契約者_携帯電話番号": lambda n: str(n).zfill(11),
    "商談希望者_電話番号": lambda n: str(n).zfill(11),
    "商談希望者_携帯電話番号": lambda n: str(n).zfill(11),
    "その他_電話番号": lambda n: str(n).zfill(11),
    "その他_携帯電話番号": lambda n: str(n).zfill(11),
    # メール系: CONCAT(LPAD(stable_key, 13, '0'), '@nyle.co.jp')
    "契約者_メールアドレス": lambda n: f"{str(n).zfill(13)}@nyle.co.jp",
    "商談希望者_メールアドレス": lambda n: f"{str(n).zfill(13)}@nyle.co.jp",
    "その他_メールアドレス": lambda n: f"{str(n).zfill(13)}@nyle.co.jp",
    # --- SQL式に含まれないカラム（独自マスク） ---
    "郵便番号": lambda n: "9999999",
    "町名・番地": lambda n: f"マスク住所_{n}",
    # LINE連絡先: URL構造を保持しつつUIDをマスク
    # 元: https://chat.line.biz/U{bot_uid}/chat/U{user_uid}
    "契約者_LINE連絡先": lambda n: f"https://chat.line.biz/U{'0' * 31}{str(n % 10).zfill(1)}/chat/U{str(n).zfill(32)}",
    "商談希望者_LINE連絡先": lambda n: f"https://chat.line.biz/U{'0' * 31}{str(n % 10).zfill(1)}/chat/U{str(n).zfill(32)}",
    "その他_LINE連絡先": lambda n: f"https://chat.line.biz/U{'0' * 31}{str(n % 10).zfill(1)}/chat/U{str(n).zfill(32)}",
    # LINE_ID: Uプレフィックス + stable_keyをゼロ埋め（LINE UIDと同形式 33文字）
    "契約者LINE_ID": lambda n: f"U{str(n).zfill(32)}",
    "商談希望者LINE_ID": lambda n: f"U{str(n).zfill(32)}",
    "その他LINE_ID": lambda n: f"U{str(n).zfill(32)}",
}

# ---------------------------------------------------------------------------
# 顧客IDカラム名（stable_key 導出元）
# ---------------------------------------------------------------------------
CUSTOMER_ID_COL = "顧客ID"


def _extract_stable_key(customer_id: str) -> int:
    """顧客IDから stable_key を導出する。

    SQL: CAST(SUBSTRING(顧客ID, 4) AS UNSIGNED)
    → Python: 4文字目以降（0-indexed で [3:]）を整数変換。
    例: "CUS0001" → 1, "CUS12345" → 12345
    """
    suffix = customer_id[3:]  # SUBSTRING(顧客ID, 4) は1-indexed → Python [3:]
    try:
        return int(suffix)
    except ValueError:
        # 数値変換できない場合はハッシュベースのフォールバック
        return abs(hash(suffix)) % 10_000_000

# ---------------------------------------------------------------------------
# フリーテキスト系カラム用: 部分一致で置換するルール
# ---------------------------------------------------------------------------
# PARTIAL_MASK_COLS に登録されたカラムに対して適用される。
# 電話番号・メール・人名・LINE URL/UID/ID を正規表現で検出し部分置換する。

# 電話番号パターン: ハイフン有り/無し、携帯・固定いずれも
_RE_PHONE = re.compile(
    r"(?<!\d)"  # 前方に数字がないことを確認
    r"(?:"
    r"0[789]0[- ]?\d{4}[- ]?\d{4}"  # 携帯 (070/080/090)
    r"|0\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4}"  # 固定電話
    r")"
    r"(?!\d)"  # 後方に数字がないことを確認
)

# メールアドレスパターン
_RE_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# 人名パターン: 「〇〇様」「〇〇 様」「〇〇　さま」「〇〇さん」等
# 姓名は漢字・ひらがな・カタカナ 1〜10文字を想定
# 「お客様」「皆様」等の一般敬語表現は除外する
# 前方に日本語文字が続いていない位置でのみマッチさせる（名前の切れ目を検出）
_RE_PERSON_NAME = re.compile(
    r"(?<![^\s\u3000、。・,.!?！？「」『』（）\(\)\n:：])"  # 前方が区切り文字・空白・行頭
    r"([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]{1,10})"  # 名前部分（中黒U+30FBを除外）
    r"([\s\u3000]*)"  # 半角/全角スペース（任意）- キャプチャして保持
    r"(様|さま|さん|サマ)"  # 敬称
)

# 人名として誤検出しやすい一般表現の除外リスト
_NAME_EXCLUSIONS = frozenset([
    "お客", "皆", "担当者", "契約者", "ご担当", "関係者",
    "奥", "御", "先生", "各位", "ご本人", "お父", "お母",
    "ご家族", "ご契約者", "お子", "ご主人", "弊社", "御社",
])

# LINE連絡先URLパターン:
# https://chat.line.biz/U{bot_uid}/chat/U{user_uid}
# UIDは U + 英数字32文字（hex形式）
_RE_LINE_CHAT_URL = re.compile(
    r"https://chat\.line\.biz/U[0-9a-f]{32}/chat/U[0-9a-f]{32}"
)

# LINE ID パターン:
# LINE UIDは U + 英数字32文字（hex形式）。フリーテキスト内に単独で出現するケース。
# 一般的な LINE ID（ユーザー設定ID）は 4〜20文字だが、
# システム上のUID（Uxxxxxxxx...）は33文字固定。両方に対応する。
_RE_LINE_UID = re.compile(
    r"(?<![a-zA-Z0-9_.\-@/])"  # 前方にURL構成文字がないことを確認（URLは別パターンで先に処理）
    r"(U[0-9a-f]{32})"
    r"(?![a-zA-Z0-9_.\-@/])"
)

# LINE ID パターン（ユーザー設定ID）:
# 先頭は英字。一般的な英単語（LINE, ID等）との誤検出を避けるため、
# 「英字+数字混在」または「大文字+小文字始まり」パターンに限定する。
# 典型例: Uzzzzzzz, takeshi.line, u_abc123
_RE_LINE_ID = re.compile(
    r"(?<![a-zA-Z0-9_.\-@])"  # 前方にID構成文字やメールの@がないことを確認
    r"("
    r"(?=[a-zA-Z])"  # 先頭は英字
    r"(?="  # 先読み: 英字+数字混在 or 小文字含む4文字以上
    r"(?:[a-zA-Z0-9_.\-]*\d[a-zA-Z0-9_.\-]*[a-zA-Z][a-zA-Z0-9_.\-]*"  # 数字と英字が混在
    r"|[a-zA-Z0-9_.\-]*[a-z][a-zA-Z0-9_.\-]*\d[a-zA-Z0-9_.\-]*"  # 小文字+数字混在
    r"|[A-Z][a-z][a-zA-Z0-9_.\-]{2,18}"  # 大文字+小文字始まり (Uzzzzzzz パターン)
    r")"
    r")"
    r"[a-zA-Z0-9_.\-]{4,20}"
    r")"
    r"(?![a-zA-Z0-9_.\-@])"  # 後方にID構成文字やメールの@がないことを確認
)


def _mask_template_field(text: str, seq_n: int) -> tuple[str, dict[str, list[tuple[str, str]]]]:
    """フリーテキスト系カラムのテキストを部分置換する。

    Returns:
        (masked_text, replacements_dict)
        replacements_dict は {"phone": [(orig, masked), ...], ...} 形式で
        マッピング記録用。
    """
    replacements: dict[str, list[tuple[str, str]]] = {
        "phone": [],
        "email": [],
        "name": [],
        "line_url": [],
        "line_uid": [],
        "line_id": [],
    }

    # --- 電話番号 ---
    phone_counter = 0

    def _replace_phone(m: re.Match) -> str:
        nonlocal phone_counter
        phone_counter += 1
        orig = m.group(0)
        masked = f"0900000{seq_n:03d}{phone_counter:02d}"
        replacements["phone"].append((orig, masked))
        return masked

    text = _RE_PHONE.sub(_replace_phone, text)

    # --- メールアドレス ---
    email_counter = 0

    def _replace_email(m: re.Match) -> str:
        nonlocal email_counter
        email_counter += 1
        orig = m.group(0)
        masked = f"template_{seq_n:06d}_{email_counter}@example.com"
        replacements["email"].append((orig, masked))
        return masked

    text = _RE_EMAIL.sub(_replace_email, text)

    # --- 人名（敬称付き） ---
    name_counter = 0

    def _replace_name(m: re.Match) -> str:
        nonlocal name_counter
        orig = m.group(0)
        name_part = m.group(1)
        space = m.group(2)
        suffix = m.group(3)
        # 一般敬語表現は除外（完全一致 or 末尾一致）
        if name_part in _NAME_EXCLUSIONS or any(
            name_part.endswith(exc) for exc in _NAME_EXCLUSIONS
        ):
            return orig
        name_counter += 1
        masked_name = f"顧客{seq_n:04d}_{name_counter}"
        masked = f"{masked_name}{space}{suffix}"
        replacements["name"].append((orig, masked))
        return masked

    text = _RE_PERSON_NAME.sub(_replace_name, text)

    # --- LINE連絡先URL ---
    line_url_counter = 0

    def _replace_line_url(m: re.Match) -> str:
        nonlocal line_url_counter
        line_url_counter += 1
        orig = m.group(0)
        bot_uid = "U" + "0" * 31 + str(seq_n % 10)
        user_uid = "U" + str(seq_n).zfill(32)
        masked = f"https://chat.line.biz/{bot_uid}/chat/{user_uid}"
        replacements["line_url"].append((orig, masked))
        return masked

    text = _RE_LINE_CHAT_URL.sub(_replace_line_url, text)

    # --- LINE UID (U + hex32桁) ---
    line_uid_counter = 0

    def _replace_line_uid(m: re.Match) -> str:
        nonlocal line_uid_counter
        line_uid_counter += 1
        orig = m.group(0)
        masked = f"U{str(seq_n).zfill(30)}{str(line_uid_counter).zfill(2)}"
        replacements["line_uid"].append((orig, masked))
        return masked

    text = _RE_LINE_UID.sub(_replace_line_uid, text)

    # --- LINE ID（ユーザー設定ID） ---
    line_counter = 0

    def _replace_line_id(m: re.Match) -> str:
        nonlocal line_counter
        line_counter += 1
        orig = m.group(0)
        masked = f"U{str(seq_n).zfill(30)}{str(line_counter).zfill(2)}"
        replacements["line_id"].append((orig, masked))
        return masked

    text = _RE_LINE_ID.sub(_replace_line_id, text)

    return text, replacements


# ---------------------------------------------------------------------------
# マッピング CSV 関連
# ---------------------------------------------------------------------------
MAP_KEY_COL = "key"
MAP_SEQ_COL = "seq"

# ---------------------------------------------------------------------------
# 部分置換対象カラム（テンプレ・コメント等のフリーテキスト系）
# ---------------------------------------------------------------------------
# ここにカラム名を追加するだけで、同じ部分置換ロジックが適用される。
PARTIAL_MASK_COLS: list[str] = [
    "初回商談時テンプレ",
    "返却コメント",
    "備考欄",
    "通信欄",
]




def load_mapping(path: Path) -> tuple[dict[str, dict[str, str]], list[str], int]:
    """既存マッピングを読み込み、(key -> entry, 既存列順, max_seq) を返す."""
    mapping: dict[str, dict[str, str]] = {}
    existing_cols: list[str] = []
    max_seq = 0
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        existing_cols = [
            c for c in (reader.fieldnames or []) if c not in (MAP_KEY_COL, MAP_SEQ_COL)
        ]
        for row in reader:
            key = row.get(MAP_KEY_COL, "")
            if not key:
                continue
            mapping[key] = dict(row)
            try:
                seq = int(row.get(MAP_SEQ_COL) or 0)
            except ValueError:
                seq = 0
            max_seq = max(max_seq, seq)
    return mapping, existing_cols, max_seq


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="マスク対象CSV")
    parser.add_argument(
        "mapping",
        nargs="?",
        help="既存マッピングCSV（任意）。指定時は再利用し、差分のみを出力",
    )
    parser.add_argument(
        "--key",
        default="レコード番号",
        help="入力CSVの一意キー列名（既定: レコード番号）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_path = input_path.with_name(f"{input_path.stem}_masked_{timestamp}.csv")
    delta_path = input_path.with_name(f"{input_path.stem}_mapping_{timestamp}.csv")

    existing: dict[str, dict[str, str]] = {}
    existing_cols: list[str] = []
    seq = 0
    if args.mapping:
        existing, existing_cols, seq = load_mapping(Path(args.mapping))

    with input_path.open(encoding="utf-8-sig") as fin:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if args.key not in fieldnames:
        raise SystemExit(
            f"キー列 '{args.key}' が input.csv に存在しません。--key で指定し直してください。"
        )

    # 入力CSVに含まれる且つMASK_RULESに定義されたカラムのみ処理対象
    target_cols = [c for c in MASK_RULES if c in fieldnames]

    # 顧客IDカラムが存在するか確認（stable_key導出用）
    has_customer_id = CUSTOMER_ID_COL in fieldnames

    # 部分置換対象カラムのうち、入力CSVに存在するもの
    active_partial_cols = [c for c in PARTIAL_MASK_COLS if c in fieldnames]

    # マッピングCSVの列順: 既存列を先頭に保持 + 今回新たに増える列
    map_cols = [MAP_KEY_COL, MAP_SEQ_COL] + existing_cols[:]
    for col in target_cols:
        if col not in map_cols:
            map_cols.append(col)

    delta_keys: list[str] = []  # 差分出力するキー（順序保持・重複排除）
    delta_keys_set: set[str] = set()

    with output_path.open("w", encoding="utf-8-sig", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            key = row.get(args.key, "")
            if not key:
                writer.writerow(row)
                continue

            if key in existing:
                entry = existing[key]
                try:
                    seq_n = int(entry.get(MAP_SEQ_COL) or 0)
                except ValueError:
                    seq_n = 0

                # stable_key を導出（顧客IDがあればそちらを優先）
                if has_customer_id:
                    customer_id = row.get(CUSTOMER_ID_COL, "")
                    stable_key = _extract_stable_key(customer_id) if customer_id else seq_n
                else:
                    stable_key = seq_n

                has_new = False

                # --- カラム全体マスク ---
                for col in target_cols:
                    original = row.get(col, "")
                    if not original:
                        continue
                    masked = entry.get(col)
                    if not masked:
                        masked = MASK_RULES[col](stable_key)
                        entry[col] = masked
                        has_new = True
                    row[col] = masked

                # --- 部分置換（フリーテキスト系カラム） ---
                for col in active_partial_cols:
                    text = row.get(col, "")
                    if text:
                        masked_text, repls = _mask_template_field(text, stable_key)
                        if any(repls.values()):
                            row[col] = masked_text
                            has_new = True

                if has_new and key not in delta_keys_set:
                    delta_keys.append(key)
                    delta_keys_set.add(key)
            else:
                seq += 1
                entry = {MAP_KEY_COL: key, MAP_SEQ_COL: str(seq)}

                # stable_key を導出（顧客IDがあればそちらを優先）
                if has_customer_id:
                    customer_id = row.get(CUSTOMER_ID_COL, "")
                    stable_key = _extract_stable_key(customer_id) if customer_id else seq
                else:
                    stable_key = seq

                # --- カラム全体マスク ---
                for col in target_cols:
                    original = row.get(col, "")
                    if original:
                        masked = MASK_RULES[col](stable_key)
                        row[col] = masked
                        entry[col] = masked
                    else:
                        entry[col] = ""

                # --- 部分置換（フリーテキスト系カラム） ---
                for col in active_partial_cols:
                    text = row.get(col, "")
                    if text:
                        masked_text, repls = _mask_template_field(text, stable_key)
                        if any(repls.values()):
                            row[col] = masked_text

                existing[key] = entry
                delta_keys.append(key)
                delta_keys_set.add(key)

            writer.writerow(row)

    if delta_keys:
        with delta_path.open("w", encoding="utf-8-sig", newline="") as fmap:
            mw = csv.DictWriter(fmap, fieldnames=map_cols, extrasaction="ignore")
            mw.writeheader()
            for k in delta_keys:
                mw.writerow(existing[k])
        print(f"マッピング差分: {delta_path} ({len(delta_keys)} 件)")
    else:
        print("マッピング差分: なし（新規差分なし）")

    print(f"マスク済み: {output_path} ({len(rows)} 行)")


if __name__ == "__main__":
    main()
