#!/usr/bin/env python3.12
"""
filter-gws-drive-metadata: Drive APIのNDJSON出力をパース・フィルタリングする

目的:
    gws drive files list --page-all の出力（NDJSON）を読み込み、
    フィルタリング・優先度判定を行い、結果をJSON形式で出力する。
    エージェントのコンテキストウィンドウ消費を抑制するために使用する。

使い方:
    gws drive files list --page-all --params '{...}' 2>/dev/null | python3.12 ~/scripts/filter-gws-drive-metadata.py
    python3.12 ~/scripts/filter-gws-drive-metadata.py --input tmp/slides_metadata.ndjson
    python3.12 ~/scripts/filter-gws-drive-metadata.py --input tmp/docs_metadata.ndjson --top 5
    python3.12 ~/scripts/filter-gws-drive-metadata.py --input tmp/docs_metadata.ndjson --owner-email user_name@example.co.jp
    python3.12 ~/scripts/filter-gws-drive-metadata.py --input tmp/docs_metadata.ndjson --output tmp/docs_filtered.json

出力:
    stdoutにはサマリー + top_files のみ出力（コンテキスト節約）。
    --output 指定時は全結果（all_files含む）をファイルに書き出す。

依存: python3.12（標準ライブラリのみ）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
import re
from typing import Any

# ─── 定数 ────────────────────────────────────────────────────────

DEFAULT_TOP_COUNT = 3

# 除外パターン（ファイル名に含まれる場合に除外候補）
EXCLUDE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"テンプレート", re.IGNORECASE),
    re.compile(r"template", re.IGNORECASE),
    re.compile(r"コピー", re.IGNORECASE),
    re.compile(r"\btest\b", re.IGNORECASE),
    re.compile(r"テスト", re.IGNORECASE),
    re.compile(r"\bsandbox\b", re.IGNORECASE),
]

# 個人メモ判定パターン（共有範囲が限定的な場合のみ除外）
PERSONAL_MEMO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"メモ", re.IGNORECASE),
    re.compile(r"\bmemo\b", re.IGNORECASE),
    re.compile(r"下書き", re.IGNORECASE),
    re.compile(r"\bdraft\b", re.IGNORECASE),
]

# 優先キーワード（ファイル名に含まれる場合に優先度UP）
PRIORITY_KEYWORDS: list[str] = [
    "方針", "戦略", "計画", "報告", "レビュー", "振り返り",
    "KPI", "OKR", "予算", "ロードマップ", "提案", "承認",
    "議事録", "Meeting notes", "定例", "全社", "経営",
]


# ─── NDJSONパース ────────────────────────────────────────────────

def parse_ndjson(source) -> list[dict[str, Any]]:
    """NDJSON（1行1JSON）をパースし、全ファイルを結合して返す。"""
    files: list[dict[str, Any]] = []
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            page = json.loads(line)
            files.extend(page.get("files", []))
        except json.JSONDecodeError:
            # stderr混入行等をスキップ
            continue
    return files


# ─── フィルタリング ──────────────────────────────────────────────

def should_exclude(file: dict[str, Any], owner_email: str | None) -> tuple[bool, str]:
    """ファイルを除外すべきか判定する。除外理由も返す。"""
    name = file.get("name", "")

    # 自分がオーナーのドキュメントを除外
    if owner_email:
        owners = file.get("owners", [])
        for owner in owners:
            if owner.get("emailAddress", "").lower() == owner_email.lower():
                return True, "self-owned"

    # テンプレート・テスト等の除外
    for pattern in EXCLUDE_PATTERNS:
        if pattern.search(name):
            return True, f"pattern:{pattern.pattern}"

    # 個人メモ判定（shared=falseの場合のみ除外）
    if not file.get("shared", False):
        for pattern in PERSONAL_MEMO_PATTERNS:
            if pattern.search(name):
                return True, f"personal:{pattern.pattern}"

    return False, ""


def calculate_priority_score(file: dict[str, Any]) -> int:
    """ファイルの優先度スコアを計算する（高いほど優先）。"""
    score = 0
    name = file.get("name", "")

    # 優先キーワードマッチ
    for keyword in PRIORITY_KEYWORDS:
        if keyword.lower() in name.lower():
            score += 10

    # 共有されている場合は優先度UP
    if file.get("shared", False):
        score += 5

    # sharingUserがいる場合（他者から共有された）
    if file.get("sharingUser"):
        score += 3

    return score


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    input_file: str | None = None
    output_file: str | None = None
    top_count = DEFAULT_TOP_COUNT
    owner_email: str | None = None

    i = 0
    while i < len(args):
        if args[i] == "--input":
            i += 1
            if i >= len(args):
                print("Error: --input requires a file path", file=sys.stderr)
                sys.exit(1)
            input_file = args[i]
        elif args[i] == "--output":
            i += 1
            if i >= len(args):
                print("Error: --output requires a file path", file=sys.stderr)
                sys.exit(1)
            output_file = args[i]
        elif args[i] == "--top":
            i += 1
            if i >= len(args):
                print("Error: --top requires a number", file=sys.stderr)
                sys.exit(1)
            top_count = int(args[i])
        elif args[i] == "--owner-email":
            i += 1
            if i >= len(args):
                print("Error: --owner-email requires an email", file=sys.stderr)
                sys.exit(1)
            owner_email = args[i]
        elif args[i] in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{args[i]}'", file=sys.stderr)
            sys.exit(1)
        i += 1

    # NDJSON読み込み
    try:
        if input_file:
            with open(input_file, encoding="utf-8") as f:
                all_files = parse_ndjson(f)
        else:
            all_files = parse_ndjson(sys.stdin)
    except FileNotFoundError:
        print(f"Error: file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # フィルタリング
    filtered: list[dict[str, Any]] = []
    excluded_count = 0
    exclude_reasons: dict[str, int] = {}

    for file in all_files:
        excluded, reason = should_exclude(file, owner_email)
        if excluded:
            excluded_count += 1
            exclude_reasons[reason] = exclude_reasons.get(reason, 0) + 1
        else:
            filtered.append(file)

    # 優先度スコア計算＋ソート
    for file in filtered:
        file["_priority_score"] = calculate_priority_score(file)

    filtered.sort(key=lambda f: f["_priority_score"], reverse=True)

    # 上位N件を抽出
    top_files = filtered[:top_count]

    # 出力用にスコアフィールドを除去
    for file in filtered:
        del file["_priority_score"]

    # all_files（軽量メタデータ）
    all_files_slim = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "modifiedTime": f.get("modifiedTime"),
            "createdTime": f.get("createdTime"),
            "owners": [o.get("displayName", "") for o in f.get("owners", [])],
            "lastModifyingUser": (f.get("lastModifyingUser") or {}).get("displayName", ""),
            "shared": f.get("shared", False),
            "webViewLink": f.get("webViewLink"),
        }
        for f in filtered
    ]

    # --output 指定時: 全結果をファイルに書き出し
    if output_file:
        full_result = {
            "summary": {
                "total_count": len(all_files),
                "filtered_count": len(filtered),
                "excluded_count": excluded_count,
                "exclude_reasons": exclude_reasons,
                "top_count": len(top_files),
            },
            "top_files": top_files,
            "all_files": all_files_slim,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(full_result, f, ensure_ascii=False, indent=2)

    # stdout: サマリー + top_files のみ（コンテキスト節約）
    stdout_result = {
        "summary": {
            "total_count": len(all_files),
            "filtered_count": len(filtered),
            "excluded_count": excluded_count,
            "exclude_reasons": exclude_reasons,
            "top_count": len(top_files),
        },
        "top_files": top_files,
    }

    # --output 未指定時のみ all_files を stdout に含める（後方互換）
    if not output_file:
        stdout_result["all_files"] = all_files_slim

    print(json.dumps(stdout_result, ensure_ascii=False, indent=2))



if __name__ == "__main__":
    main()
