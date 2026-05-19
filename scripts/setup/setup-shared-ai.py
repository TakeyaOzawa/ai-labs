#!/usr/bin/env python3.12
"""
setup: 開発環境の統合セットアップ

環境変数チェックとsymlink構築を順番に実行する。
環境変数に不足がある場合はエラーで中断する。

Usage:
    python3.12 ~/scripts/setup-shared-ai.py            # フルセットアップ
    python3.12 ~/scripts/setup-shared-ai.py --verify   # 現在の状態を検証
    python3.12 ~/scripts/setup-shared-ai.py --dry-run  # 実行内容の確認のみ

終了コード:
    0: 全て正常
    1: 環境変数チェックまたはsymlinkセットアップに失敗
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import subprocess

SCRIPTS_DIR = Path(__file__).parent


def run_script(script_name: str, args: list[str] | None = None) -> int:
    """サブスクリプトを実行して終了コードを返す。"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"❌ {script_path} が見つかりません")
        return 1

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    result = subprocess.run(cmd, cwd=str(SCRIPTS_DIR))
    return result.returncode


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="開発環境の統合セットアップ（環境変数チェック + symlink構築）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実行内容を表示するのみ（変更なし）",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="現在の状態を検証する",
    )
    args = parser.parse_args()

    has_error = False

    # Step 1: 環境変数チェック
    rc = run_script("check-env.py")
    if rc != 0:
        has_error = True
        print()
        print("⚠️  環境変数に不足があります。上記の修正手順を実施してください。")
        print("   修正後に再度 setup-shared-ai.py を実行してください。")
        print()
        print("─" * 50)
        print()

    # Step 2: symlink セットアップ
    symlink_args: list[str] = []
    if args.dry_run:
        symlink_args.append("--dry-run")
    if args.verify:
        symlink_args.append("--verify")

    rc = run_script("setup-symlinks.py", symlink_args or None)
    if rc != 0:
        has_error = True

    # Step 3: 構造検証
    if not args.dry_run:
        print()
        print("─" * 50)
        print()
        rc = run_script("verify-shared-ai-structure.py", ["--quick"])
        if rc != 0:
            has_error = True

    # 結果サマリー
    print()
    if has_error:
        print("⚠️  セットアップに問題があります。上記の出力を確認してください。")
        sys.exit(1)
    else:
        print("✅ セットアップ完了")



if __name__ == "__main__":
    main()
