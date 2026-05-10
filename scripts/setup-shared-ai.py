#!/usr/bin/env python3.12
"""
shared-ai セットアップスクリプト

git clone 後に実行し、各AIツールからのsymlink参照を構築する。
冪等性あり（何度実行しても安全）。

Usage:
    python3.12 ~/scripts/setup-shared-ai.py
    python3.12 ~/scripts/setup-shared-ai.py --dry-run   # 実行内容の確認のみ
    python3.12 ~/scripts/setup-shared-ai.py --verify    # 現在の状態を検証
"""

import argparse
import os
import sys
from pathlib import Path

HOME = Path.home()
SHARED_AI = HOME / ".shared-ai"


# === symlink定義 ===

# ディレクトリsymlink: link_path → target_path
DIRECTORY_SYMLINKS = [
    {
        "link": HOME / ".kiro" / "skills",
        "target": SHARED_AI / "skills",
        "description": "Kiro skills",
    },
    {
        "link": HOME / ".claude" / "skills",
        "target": SHARED_AI / "skills",
        "description": "Claude Code skills",
    },
    {
        "link": HOME / ".agents" / "skills",
        "target": SHARED_AI / "skills",
        "description": ".agents skills (Google)",
    },
]

# 個別ファイルsymlink: link_path → target_path
FILE_SYMLINKS = [
    {
        "link": HOME / ".codex" / "rules" / "dev-environment.md",
        "target": SHARED_AI / "rules" / "dev-environment.md",
        "description": "Codex rule: dev-environment",
    },
    {
        "link": HOME / ".codex" / "rules" / "gws-integration.md",
        "target": SHARED_AI / "rules" / "gws-integration.md",
        "description": "Codex rule: gws-integration",
    },
    {
        "link": HOME / ".codex" / "rules" / "python-coding-standards.md",
        "target": SHARED_AI / "rules" / "python-coding-standards.md",
        "description": "Codex rule: python-coding-standards",
    },
    {
        "link": HOME / ".codex" / "rules" / "shell-coding-standards.md",
        "target": SHARED_AI / "rules" / "shell-coding-standards.md",
        "description": "Codex rule: shell-coding-standards",
    },
    {
        "link": HOME / ".codex" / "rules" / "pr-creation.md",
        "target": SHARED_AI / "rules" / "pr-creation.md",
        "description": "Codex rule: pr-creation",
    },
]


def create_symlink(link: Path, target: Path, description: str, dry_run: bool) -> bool:
    """symlinkを作成する。既に正しいsymlinkが存在する場合はスキップ。"""
    if link.is_symlink():
        current_target = link.resolve()
        expected_target = target.resolve()
        if current_target == expected_target:
            print(f"  ✓ {description}: 既に正しいsymlink")
            return True
        else:
            print(f"  ⚠ {description}: symlink先が異なる")
            print(f"    現在: {link} -> {os.readlink(link)}")
            print(f"    期待: {link} -> {target}")
            if not dry_run:
                link.unlink()
                link.symlink_to(target)
                print(f"    → 修正完了")
            return not dry_run

    if link.exists():
        # 実体ディレクトリ/ファイルが存在する場合
        print(f"  ⚠ {description}: 実体が存在（symlinkではない）")
        print(f"    パス: {link}")
        if not dry_run:
            backup = link.with_suffix(link.suffix + ".bak")
            if backup.exists():
                print(f"    バックアップ {backup} が既に存在。手動確認が必要")
                return False
            link.rename(backup)
            link.symlink_to(target)
            print(f"    → バックアップ作成: {backup}")
            print(f"    → symlink作成完了")
        else:
            print(f"    → (dry-run) バックアップ後にsymlink作成予定")
        return not dry_run

    # 存在しない場合: 親ディレクトリを作成してsymlink作成
    if not dry_run:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        print(f"  ✓ {description}: symlink作成完了")
    else:
        print(f"  → (dry-run) {description}: symlink作成予定")
        print(f"    {link} -> {target}")
    return not dry_run


def verify_symlinks() -> bool:
    """全symlinkの状態を検証する。"""
    print("=== symlink検証 ===\n")
    all_ok = True

    print("[ディレクトリsymlink]")
    for item in DIRECTORY_SYMLINKS:
        link = item["link"]
        target = item["target"]
        desc = item["description"]

        if not target.exists():
            print(f"  ✗ {desc}: ターゲットが存在しない ({target})")
            all_ok = False
        elif link.is_symlink():
            actual = Path(os.readlink(link))
            if actual == target or link.resolve() == target.resolve():
                print(f"  ✓ {desc}: OK ({link} -> {target})")
            else:
                print(f"  ✗ {desc}: symlink先が不正 ({link} -> {actual})")
                all_ok = False
        elif link.exists():
            print(f"  ✗ {desc}: 実体ディレクトリ（symlinkではない）")
            all_ok = False
        else:
            print(f"  ✗ {desc}: 存在しない")
            all_ok = False

    print("\n[ファイルsymlink]")
    for item in FILE_SYMLINKS:
        link = item["link"]
        target = item["target"]
        desc = item["description"]

        if not target.exists():
            print(f"  ✗ {desc}: ターゲットが存在しない ({target})")
            all_ok = False
        elif link.is_symlink():
            actual = Path(os.readlink(link))
            if actual == target or link.resolve() == target.resolve():
                print(f"  ✓ {desc}: OK")
            else:
                print(f"  ✗ {desc}: symlink先が不正 ({actual})")
                all_ok = False
        elif link.exists():
            print(f"  ✗ {desc}: 実体ファイル（symlinkではない）")
            all_ok = False
        else:
            print(f"  ✗ {desc}: 存在しない")
            all_ok = False

    print()
    if all_ok:
        print("✅ 全symlink正常")
    else:
        print("⚠️  問題あり。`python3.12 ~/.shared-ai/setup.py` で修復してください")
    return all_ok


def setup(dry_run: bool) -> None:
    """セットアップを実行する。"""
    mode = "(dry-run) " if dry_run else ""
    print(f"=== {mode}shared-ai symlink セットアップ ===\n")

    # ターゲットの存在確認
    if not SHARED_AI.exists():
        print(f"✗ エラー: {SHARED_AI} が存在しません。")
        print("  git clone 後にこのスクリプトを実行してください。")
        sys.exit(1)

    if not (SHARED_AI / "skills").exists():
        print(f"✗ エラー: {SHARED_AI / 'skills'} が存在しません。")
        sys.exit(1)

    if not (SHARED_AI / "rules").exists():
        print(f"✗ エラー: {SHARED_AI / 'rules'} が存在しません。")
        sys.exit(1)

    # ディレクトリsymlink
    print("[ディレクトリsymlink]")
    for item in DIRECTORY_SYMLINKS:
        create_symlink(item["link"], item["target"], item["description"], dry_run)

    # ファイルsymlink
    print("\n[ファイルsymlink]")
    for item in FILE_SYMLINKS:
        create_symlink(item["link"], item["target"], item["description"], dry_run)

    print()
    if dry_run:
        print("(dry-run完了。実際に実行するには --dry-run を外してください)")
    else:
        print("✅ セットアップ完了")
        print()
        print("検証: python3.12 ~/.shared-ai/setup.py --verify")


def main():
    parser = argparse.ArgumentParser(
        description="shared-ai symlink セットアップ"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実行内容を表示するのみ（変更なし）",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="現在のsymlink状態を検証する",
    )
    args = parser.parse_args()

    if args.verify:
        ok = verify_symlinks()
        sys.exit(0 if ok else 1)
    else:
        setup(dry_run=args.dry_run)



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
