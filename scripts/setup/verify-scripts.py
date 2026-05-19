#!/usr/bin/env python3.12
"""
verify-scripts: 全スクリプトのシンタックスチェック + import検証

目的:
    scripts/ 配下の全 .py ファイルに対して:
    1. シンタックスエラーがないこと（py_compile）
    2. モジュールとしてimport可能であること（importlib）
    を一括検証する。リファクタリング後の動作確認に使用。

使い方:
    python3.12 scripts/setup/verify-scripts.py              # 全チェック
    python3.12 scripts/setup/verify-scripts.py --syntax     # シンタックスのみ
    python3.12 scripts/setup/verify-scripts.py --import     # importのみ
    python3.12 scripts/setup/verify-scripts.py --dir gws    # 特定ディレクトリのみ
    python3.12 scripts/setup/verify-scripts.py --verbose    # 成功も表示

終了コード:
    0: 全ファイルOK
    1: エラーあり
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import importlib.util
import io
import os
import py_compile
import traceback

# ─── 定数 ────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SUBDIRS = ["pipelines", "jobs", "slack", "gws", "data", "rss", "ai", "setup", "utils", "lib"]
EXCLUDE_FILES = {"__init__.py", "conftest.py"}
EXCLUDE_DIRS = {"old", "tests", "__pycache__", ".pytest_cache", ".venv"}

# import検証で既知の正常エラーを許容するファイル
IMPORT_KNOWN_ISSUES: set[str] = set()


# ─── チェックロジック ─────────────────────────────────────────────

def check_syntax(file_path: Path) -> tuple[bool, str]:
    """py_compile でシンタックスチェック。"""
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)


def check_import(file_path: Path) -> tuple[bool, str]:
    """importlib でモジュールロード可能か検証。

    SystemExit（argparse等）は正常終了扱い。
    lib/ 内のモジュールはパッケージimportで検証する。
    """
    # 既知の問題ファイルはスキップ
    if file_path.name in IMPORT_KNOWN_ISSUES:
        return True, "(skipped: known issue)"

    # scripts/ を sys.path に追加（エントリポイントが期待する環境を再現）
    scripts_str = str(SCRIPTS_DIR)
    lib_str = str(SCRIPTS_DIR / "lib")
    original_path = sys.path[:]
    original_modules = set(sys.modules.keys())

    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)

    try:
        # lib/ 内のモジュールはパッケージとしてimport
        if file_path.parent.name == "lib":
            module_name = f"lib.{file_path.stem}"
            # パッケージの __init__.py を先にロード
            init_path = file_path.parent / "__init__.py"
            if init_path.exists() and "lib" not in sys.modules:
                init_spec = importlib.util.spec_from_file_location("lib", str(init_path))
                if init_spec:
                    init_mod = importlib.util.module_from_spec(init_spec)
                    sys.modules["lib"] = init_mod
                    init_spec.loader.exec_module(init_mod)

            spec = importlib.util.spec_from_file_location(
                module_name, str(file_path),
                submodule_search_locations=[],
            )
        else:
            module_name = file_path.stem.replace("-", "_")
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))

        if spec is None:
            return False, "spec is None"
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        # stdout/stderrを抑制（スクリプトのprint出力を非表示にする）
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        return True, ""
    except SystemExit:
        # argparse の --help 等で SystemExit が発生するのは正常
        return True, "(SystemExit)"
    except IndexError:
        # sys.argv[1] 等を直接参照するスクリプト（引数必須）は正常扱い
        return True, "(IndexError: requires args)"
    except Exception as e:
        tb = traceback.format_exception_only(type(e), e)
        return False, "".join(tb).strip()
    finally:
        sys.path[:] = original_path
        # ロードしたモジュールをクリーンアップ（他のテストに影響しないように）
        new_modules = set(sys.modules.keys()) - original_modules
        for m in new_modules:
            del sys.modules[m]


def collect_files(target_dirs: list[str] | None = None) -> list[Path]:
    """検証対象ファイルを収集する。"""
    files: list[Path] = []

    # ルート直下の .py ファイル
    if target_dirs is None:
        for f in SCRIPTS_DIR.glob("*.py"):
            if f.name not in EXCLUDE_FILES and not f.name.startswith("."):
                files.append(f)

    # サブディレクトリ
    dirs_to_check = target_dirs if target_dirs else SUBDIRS
    for subdir in dirs_to_check:
        d = SCRIPTS_DIR / subdir
        if not d.exists():
            continue
        for f in d.glob("*.py"):
            if f.name in EXCLUDE_FILES:
                continue
            files.append(f)

    return sorted(files)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="全スクリプトのシンタックス・import検証")
    parser.add_argument("--syntax", action="store_true", help="シンタックスチェックのみ")
    parser.add_argument("--import", dest="import_check", action="store_true", help="importチェックのみ")
    parser.add_argument("--dir", nargs="*", help="対象ディレクトリ（省略時: 全サブディレクトリ）")
    parser.add_argument("--verbose", "-v", action="store_true", help="成功も表示")
    args = parser.parse_args()

    # デフォルト: 両方実行
    do_syntax = args.syntax or (not args.syntax and not args.import_check)
    do_import = args.import_check or (not args.syntax and not args.import_check)

    files = collect_files(args.dir)
    print(f"検証対象: {len(files)} ファイル\n")

    syntax_ok = 0
    syntax_fail = 0
    import_ok = 0
    import_fail = 0
    errors: list[str] = []

    # Phase 1: シンタックスチェック
    if do_syntax:
        print("=== Phase 1: シンタックスチェック (py_compile) ===")
        for f in files:
            ok, msg = check_syntax(f)
            rel = f.relative_to(SCRIPTS_DIR)
            if ok:
                syntax_ok += 1
                if args.verbose:
                    print(f"  ✅ {rel}")
            else:
                syntax_fail += 1
                print(f"  ❌ {rel}: {msg}")
                errors.append(f"[syntax] {rel}: {msg}")

        print(f"\n  結果: ✅ {syntax_ok} / ❌ {syntax_fail}\n")

    # Phase 2: importチェック
    if do_import:
        print("=== Phase 2: importチェック (importlib) ===")
        for f in files:
            ok, msg = check_import(f)
            rel = f.relative_to(SCRIPTS_DIR)
            if ok:
                import_ok += 1
                if args.verbose:
                    suffix = f" {msg}" if msg else ""
                    print(f"  ✅ {rel}{suffix}")
            else:
                import_fail += 1
                print(f"  ❌ {rel}: {msg}")
                errors.append(f"[import] {rel}: {msg}")

        print(f"\n  結果: ✅ {import_ok} / ❌ {import_fail}\n")

    # サマリー
    total_fail = syntax_fail + import_fail
    print("=" * 50)
    if total_fail == 0:
        print(f"✅ 全 {len(files)} ファイル OK")
    else:
        print(f"❌ {total_fail} 件のエラー:")
        for e in errors:
            print(f"  {e}")

    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()
