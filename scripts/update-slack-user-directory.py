#!/usr/bin/env python3
"""
Slack ユーザーディレクトリ更新スクリプト

使い方:
  python3 scripts/update-slack-user-directory.py <input_json_dir> <output_steering_dir>

引数:
  input_json_dir:    fetch-slack-users.py で取得した all_users.json が格納されたディレクトリ
  output_steering_dir: steering出力先（例: ${HOME}/Documents/works/slack_users/2026-05-01）

このスクリプトは以下を行う:
  1. input_json_dir 内のJSONファイルを読み込み、ユーザーを統合
  2. ボット（is_bot=true）を除外
  3. active/inactive × 事業部 に分類
  4. steering用mdファイルを出力
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def classify_user(title: str, email: str) -> str:
    """ユーザーを事業部に分類する"""
    t = (title or "").upper()

    # MDX（兼任時の優先）
    mdx_keywords = [
        "MDX", "カートレーディング", "カスタマーサクセス", "ナーチャリング",
        "インシュアランス", "セールスオペレーション", "パティオ",
        "エンジニアリング統括", "エンジニアリングユニット", "BIZDEV",
        "新車サイト", "クロージング", "アウトバウンド",
    ]
    if any(k in t for k in mdx_keywords):
        return "mdx"

    # MS
    ms_keywords = [
        "MS", "APPLIV", "アプリブ", "アプリヴ", "ギルドロケット",
        "TOPICS", "ラクタ", "NYLE TRIDE", "VOD", "ライフスタイル",
        "メディアグループ", "メディアグロース", "SEO", "エンジニアリングライン",
        "アプリマーケティング", "広報",
    ]
    if any(k in t for k in ms_keywords):
        return "ms"

    # DXM
    dxm_keywords = [
        "DXM", "DX＆", "DX&", "コンサルティング", "コンテンツユニット",
        "コンテンツU", "マーケティングユニット", "PMU", "プロジェクト統括",
        "プロジェクト推進", "DGM", "コンサル", "事業支援", "事業企画",
        "オペレーションDX",
    ]
    if any(k in t for k in dxm_keywords):
        return "dxm"

    # HR
    hr_keywords = [
        "HR", "人事", "採用", "HRBP", "カルチャーデザイン", "労務", "EMT",
    ]
    if any(k in t for k in hr_keywords):
        return "hr"

    # CP
    cp_keywords = [
        "CP", "コーポレート", "経営管理", "法務", "ICT", "財務", "経理",
        "取締役", "PRESIDENT", "社長", "執行役員", "天才",
        "CD", "Culture Design", "CultureDesign", "カルチャーデザイン", "カルチャー デザイン"
    ]
    if any(k in t for k in cp_keywords):
        return "cp"

    # title空
    if not title.strip():
        if email.endswith("@nyle.co.jp") or email.endswith("@volare.jp"):
            return "nyle-unset"
        return "guests"

    return "other"


def parse_users_from_json_dir(json_dir: str) -> dict:
    """JSONディレクトリから全ユーザーを読み込む"""
    users = {}
    json_files = sorted(Path(json_dir).glob("*.json"))

    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)

        members = data if isinstance(data, list) else data.get("members", [])
        for m in members:
            if m.get("is_bot", False):
                continue
            if m.get("id") == "USLACKBOT":
                continue

            uid = m["id"]
            profile = m.get("profile", {})
            users[uid] = {
                "name": profile.get("real_name", m.get("real_name", "")),
                "title": profile.get("title", ""),
                "email": profile.get("email", ""),
                "deleted": m.get("deleted", False),
            }

    return users


def write_steering_file(path: str, title: str, desc: str, members: dict):
    """steering用mdファイルを書き出す"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        "inclusion: manual",
        "---",
        "",
        f"# {title}",
        "",
        desc,
        "",
        f"最終更新: {today} | 件数: {len(members)}",
        "",
        "```yaml",
    ]
    for uid in sorted(members.keys()):
        d = members[uid]
        lines.append(f'{uid}:')
        lines.append(f'  name: "{d["name"]}"')
        lines.append(f'  title: "{d["title"]}"')
        lines.append(f'  email: "{d["email"]}"')
    lines.append("```")
    lines.append("")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))

    return len(members)


DIV_META = {
    "mdx": ("MDX事業部", "自動車産業DX事業部（セールス、CS、エンジニアリング、ナーチャリング等）"),
    "dxm": ("DXM事業部", "DX＆マーケティング事業部（コンサルティング、コンテンツ、PMU等）"),
    "ms": ("MS事業部", "メディア＆ソリューション事業部（Appliv、ギルドロケット、TOPICS等）"),
    "hr": ("HR（人事本部）", "人事本部（採用、労務、HRBP、カルチャーデザイン室等）"),
    "cp": ("CP（コーポレート本部）", "コーポレート本部（経営管理、法務、ICT推進、経営層等）、CD室"),
    "nyle-unset": ("ナイル社員（所属未設定）", "nyle.co.jp/volare.jpメールだがtitleが未設定のメンバー"),
    "other": ("その他所属", "title設定ありだが主要事業部に分類されないメンバー"),
    "guests": ("外部ゲスト", "外部パートナー・ゲストアカウント"),
}


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_json_dir> <output_steering_dir>")
        sys.exit(1)

    json_dir = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Input:  {json_dir}")
    print(f"Output: {output_dir}")

    # Parse
    users = parse_users_from_json_dir(json_dir)
    print(f"Total users (excl. bots): {len(users)}")

    active = {uid: d for uid, d in users.items() if not d["deleted"]}
    inactive = {uid: d for uid, d in users.items() if d["deleted"]}
    print(f"  Active: {len(active)}, Inactive: {len(inactive)}")

    # Classify & write
    for status, pool, status_label in [
        ("active", active, "アクティブユーザー"),
        ("inactive", inactive, "非アクティブユーザー"),
    ]:
        divisions = {k: {} for k in DIV_META}
        for uid, data in pool.items():
            div = classify_user(data["title"], data["email"])
            divisions[div][uid] = data

        print(f"\n  [{status_label}]")
        for div_key, members in divisions.items():
            if not members:
                continue
            label, desc_base = DIV_META[div_key]
            title = f"Slack {status_label}: {label}"
            desc = f"{desc_base}の{status_label}。"
            if status == "inactive":
                desc += "過去の投稿者特定等に使用。"

            path = os.path.join(output_dir, status, f"{div_key}.md")
            count = write_steering_file(path, title, desc, members)
            print(f"    {div_key}: {count} users -> {path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
