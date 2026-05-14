#!/usr/bin/env python3.12
"""マスク済みCSVからテストデータ用INSERT SQLを生成するスクリプト.

使い方:
    generate-negotiation-records-sql.py <masked-input.csv> [--output <output.sql>]

挙動:
- CSVから member_id（顧客ID）と management_id（会員No）を読み込み、
  各テーブルへのINSERT文をセクションごとに1文で生成する。
- レコード数に応じてバリエーションを自動的に割り当てる。
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 設定（必要に応じて変更）
# ---------------------------------------------------------------------------

CSV_MEMBER_ID_COL = "顧客ID"
CSV_MANAGEMENT_ID_COL = "会員No"

STAFF_ID = 50
CREATED_BY = "drm_daily_migrate_test"
UPDATED_BY = "drm_daily_migrate_test"

# ---------------------------------------------------------------------------
# バリエーション定義
# レコードを母数で均等分割し、各グループに異なるパラメータを割り当てる。
# ---------------------------------------------------------------------------

# negotiations: product_category_id のバリエーション
NEGOTIATION_VARIANTS = [
    {"product_category_id": 1, "negotiation_progress_status_id": "NULL"},
    {"product_category_id": 1, "negotiation_progress_status_id": "1"},
    {"product_category_id": 1, "negotiation_progress_status_id": "2"},
]

# negotiation_assignee_map: 担当種別のバリエーション
ASSIGNEE_VARIANTS = [
    {"m_negotiation_assignee_id": 3, "staff_id": STAFF_ID},
    {"m_negotiation_assignee_id": 1, "staff_id": STAFF_ID},
    {"m_negotiation_assignee_id": 2, "staff_id": STAFF_ID},
]

# negotiation_schedule_logs: スケジュール種別のバリエーション
SCHEDULE_VARIANTS = [
    {"m_negotiation_schedule_id": 1, "scheduled_date": "CURRENT_DATE", "scheduled_time": "NULL"},
    {"m_negotiation_schedule_id": 1, "scheduled_date": "CURRENT_DATE", "scheduled_time": "'18:00'"},
    {"m_negotiation_schedule_id": 2, "scheduled_date": "DATE_ADD(CURRENT_DATE, INTERVAL 1 DAY)", "scheduled_time": "'10:00'"},
]

# contact_histories: コンタクト種別のバリエーション
CONTACT_VARIANTS = [
    {"contact_type": "customer_self", "contact_method": "lease", "contact_phase": "sales"},
    {"contact_type": "customer_other", "contact_method": "lease", "contact_phase": "sales"},
    {"contact_type": "customer_self", "contact_method": "purchase", "contact_phase": "nurturing"},
]

# contact_history_fields: フィールド値のバリエーション
CONTACT_FIELD_VARIANTS = [
    {"field_definition_id": 1, "field_value": '["TEL"]'},
    {"field_definition_id": 1, "field_value": '["TEL","不在","SMS"]'},
    {"field_definition_id": 1, "field_value": '["TEL","不在","メール","SMS","LINE","書類送付","OAC回付"]'},
]

# lost_negotiations: 失注理由のバリエーション
LOST_VARIANTS = [
    {"lost_reason_id": 25, "m_lost_reason_id": 25, "immediate_lost": 0},
    {"lost_reason_id": 10, "m_lost_reason_id": 10, "immediate_lost": 0},
    {"lost_reason_id": 5, "m_lost_reason_id": 5, "immediate_lost": 1},
]


def _pick_variant(variants: list[dict], idx: int) -> dict:
    """レコードインデックスに応じてバリエーションを均等に割り当てる。"""
    return variants[idx % len(variants)]


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="マスク済みCSV")
    parser.add_argument(
        "--output", "-o",
        help="出力SQLファイル（省略時は入力ファイル名ベースで自動生成）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = input_path.with_name(
            f"{input_path.stem}_test_data_{timestamp}.sql"
        )

    # CSV読み込み
    with input_path.open(encoding="utf-8-sig") as fin:
        reader = csv.DictReader(fin)
        rows = list(reader)

    if not rows:
        raise SystemExit("CSVにデータがありません。")

    # 必須カラム確認
    fieldnames = list(rows[0].keys())
    for col in (CSV_MEMBER_ID_COL, CSV_MANAGEMENT_ID_COL):
        if col not in fieldnames:
            raise SystemExit(f"必須カラム '{col}' がCSVに存在しません。")

    # 有効レコード抽出
    records: list[tuple[str, str]] = []
    for row in rows:
        mid = row[CSV_MEMBER_ID_COL]
        mgmt = row[CSV_MANAGEMENT_ID_COL]
        if mid and mgmt:
            records.append((mid, mgmt))

    if not records:
        raise SystemExit("有効なレコードがありません。")

    # 除外率に基づくサブセット生成
    # - negotiations: 全件
    # - negotiations 以外: 2割を除外（8割のレコードを生成）
    # - lost_xxx: 8割を除外（2割のレコードのみ生成）
    n = len(records)
    cutoff_normal = int(n * 0.8)  # 先頭80%を使用（20%除外）
    cutoff_lost = int(n * 0.2)    # 先頭20%を使用（80%除外）

    records_normal = records[:cutoff_normal]
    records_lost = records[:cutoff_lost]

    # SQL生成
    lines: list[str] = []
    lines.append(f"-- =============================================================================")
    lines.append(f"-- テストデータ INSERT SQL")
    lines.append(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"-- Source: {input_path.name}")
    lines.append(f"-- Records: {len(records)} (all)")
    lines.append(f"-- Assignee/Schedule/Contact: {cutoff_normal} records (80%)")
    lines.append(f"-- Lost: {cutoff_lost} records (20%)")
    lines.append(f"-- =============================================================================")
    lines.append("")

    lines.append(_gen_negotiations(records))
    lines.append(_gen_assignee_map(records_normal))
    lines.append(_gen_schedule_logs(records_normal))
    lines.append(_gen_contact_histories(records_normal))
    lines.append(_gen_contact_history_fields(records_normal))
    if records_lost:
        lines.append(_gen_lost_negotiations(records_lost))
        lines.append(_gen_lost_negotiation_maps(records_lost))
    else:
        lines.append("-- =============================================================================")
        lines.append("-- Section 6-7: lost_negotiations / lost_negotiation_maps — SKIPPED (0 records)")
        lines.append("-- =============================================================================")

    # 出力
    with output_path.open("w", encoding="utf-8") as fout:
        fout.write("\n".join(lines))

    print(f"SQL生成完了: {output_path} ({len(records)} レコード)")


# ---------------------------------------------------------------------------
# Section 1: negotiations（バルクINSERT）
# ---------------------------------------------------------------------------

def _gen_negotiations(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 1: negotiations",
        "-- =============================================================================",
        "INSERT INTO carmo_db.negotiations (",
        "    member_id, management_id, product_category_id,",
        "    negotiation_progress_status_id,",
        "    created_at, updated_at, deleted_at,",
        "    created_by, updated_by",
        ") VALUES",
    ]
    value_rows: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(NEGOTIATION_VARIANTS, idx)
        value_rows.append(
            f"    ('{mid}', '{mgmt}', {v['product_category_id']}, "
            f"{v['negotiation_progress_status_id']}, "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), NULL, "
            f"'{CREATED_BY}', '{UPDATED_BY}')"
        )
    lines.append(",\n".join(value_rows) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 2: negotiation_assignee_map（SELECT UNION ALL で一括INSERT）
# ---------------------------------------------------------------------------

def _gen_assignee_map(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 2: negotiation_assignee_map",
        "-- =============================================================================",
        "INSERT INTO carmo_db.negotiation_assignee_map (",
        "    negotiation_id, m_negotiation_assignee_id, staff_id,",
        "    created_at, updated_at, created_by, updated_by",
        ")",
    ]
    selects: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(ASSIGNEE_VARIANTS, idx)
        selects.append(
            f"SELECT n.negotiation_id, {v['m_negotiation_assignee_id']}, {v['staff_id']}, "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), '{CREATED_BY}', '{UPDATED_BY}' "
            f"FROM carmo_db.negotiations n "
            f"WHERE n.member_id = '{mid}' AND n.management_id = '{mgmt}'"
        )
    lines.append("\nUNION ALL\n".join(selects) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 3: negotiation_schedule_logs（SELECT UNION ALL で一括INSERT）
# ---------------------------------------------------------------------------

def _gen_schedule_logs(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 3: negotiation_schedule_logs",
        "-- =============================================================================",
        "INSERT INTO carmo_db.negotiation_schedule_logs (",
        "    negotiation_id, m_negotiation_schedule_id,",
        "    scheduled_date, scheduled_time,",
        "    created_at, updated_at, created_by, updated_by",
        ")",
    ]
    selects: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(SCHEDULE_VARIANTS, idx)
        selects.append(
            f"SELECT n.negotiation_id, {v['m_negotiation_schedule_id']}, "
            f"{v['scheduled_date']}, {v['scheduled_time']}, "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), '{CREATED_BY}', '{UPDATED_BY}' "
            f"FROM carmo_db.negotiations n "
            f"WHERE n.member_id = '{mid}' AND n.management_id = '{mgmt}'"
        )
    lines.append("\nUNION ALL\n".join(selects) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 4: contact_histories（バルクINSERT）
# ---------------------------------------------------------------------------

def _gen_contact_histories(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 4: contact_histories",
        "-- =============================================================================",
        "INSERT INTO carmo_db.contact_histories (",
        "    member_id, management_id,",
        "    contact_type, contact_date,",
        "    contact_content, contact_method, contact_status, contact_phase,",
        "    created_at, updated_at",
        ") VALUES",
    ]
    value_rows: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(CONTACT_VARIANTS, idx)
        value_rows.append(
            f"    ('{mid}', '{mgmt}', "
            f"'{v['contact_type']}', "
            f"CONCAT(CURRENT_DATE, ' 15:00:00'), "
            f"'テストデータ（自動生成）', "
            f"'{v['contact_method']}', '[]', '{v['contact_phase']}', "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())"
        )
    lines.append(",\n".join(value_rows) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 5: contact_history_fields（SELECT UNION ALL で一括INSERT）
# ---------------------------------------------------------------------------

def _gen_contact_history_fields(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 5: contact_history_fields",
        "-- =============================================================================",
        "INSERT INTO carmo_db.contact_history_fields (",
        "    contact_history_id, field_definition_id, field_value,",
        "    created_at, updated_at",
        ")",
    ]
    selects: list[str] = []
    for idx, (mid, _mgmt) in enumerate(records):
        v = _pick_variant(CONTACT_FIELD_VARIANTS, idx)
        # 各 member_id の最新 contact_history を参照
        selects.append(
            f"SELECT ch.contact_history_id, {v['field_definition_id']}, "
            f"'{v['field_value']}', "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP() "
            f"FROM carmo_db.contact_histories ch "
            f"WHERE ch.member_id = '{mid}' "
            f"AND ch.contact_content = 'テストデータ（自動生成）' "
            f"ORDER BY ch.contact_history_id DESC LIMIT 1"
        )
    # UNION ALL + LIMIT は各サブクエリに括弧が必要
    wrapped = [f"({s})" for s in selects]
    lines.append("\nUNION ALL\n".join(wrapped) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 6: lost_negotiations（SELECT UNION ALL で一括INSERT）
# ---------------------------------------------------------------------------

def _gen_lost_negotiations(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 6: lost_negotiations",
        "-- =============================================================================",
        "INSERT INTO carmo_db.lost_negotiations (",
        "    negotiation_id, lost_notes, immediate_lost, lost_reason_id,",
        "    created_at, updated_at, created_by, updated_by",
        ")",
    ]
    selects: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(LOST_VARIANTS, idx)
        selects.append(
            f"SELECT n.negotiation_id, 'テスト失注データ（自動生成）', "
            f"{v['immediate_lost']}, {v['lost_reason_id']}, "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), '{CREATED_BY}', '{UPDATED_BY}' "
            f"FROM carmo_db.negotiations n "
            f"WHERE n.member_id = '{mid}' AND n.management_id = '{mgmt}'"
        )
    lines.append("\nUNION ALL\n".join(selects) + ";")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 7: lost_negotiation_maps（SELECT UNION ALL で一括INSERT）
# ---------------------------------------------------------------------------

def _gen_lost_negotiation_maps(records: list[tuple[str, str]]) -> str:
    lines = [
        "-- =============================================================================",
        "-- Section 7: lost_negotiation_maps",
        "-- =============================================================================",
        "INSERT INTO carmo_db.lost_negotiation_maps (",
        "    lost_negotiation_id, m_lost_reason_id,",
        "    created_at, updated_at, created_by, updated_by",
        ")",
    ]
    selects: list[str] = []
    for idx, (mid, mgmt) in enumerate(records):
        v = _pick_variant(LOST_VARIANTS, idx)
        selects.append(
            f"SELECT ln.lost_negotiation_id, {v['m_lost_reason_id']}, "
            f"CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), '{CREATED_BY}', '{UPDATED_BY}' "
            f"FROM carmo_db.lost_negotiations ln "
            f"INNER JOIN carmo_db.negotiations n ON n.negotiation_id = ln.negotiation_id "
            f"WHERE n.member_id = '{mid}' AND n.management_id = '{mgmt}' "
            f"AND ln.deleted_at IS NULL"
        )
    lines.append("\nUNION ALL\n".join(selects) + ";")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
