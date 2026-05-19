#!/usr/bin/env python3.12
"""
check-platform-commands: OS依存コマンドの直接呼び出し検出

目的:
    scripts/ 配下の全 .py ファイルに対して、OS依存コマンドを
    platform-commands.sh を経由せず直接呼び出していないかを検証する。
    macOS / Ubuntu (WSL2) 両環境での動作保証を維持するためのガードレール。

使い方:
    python3.12 scripts/setup/check-platform-commands.py
    python3.12 scripts/setup/check-platform-commands.py --verbose
    python3.12 scripts/setup/check-platform-commands.py --dir jobs slack

例:
    python3.12 scripts/setup/check-platform-commands.py --verbose

出力: JSON（成功/失敗 + 検出箇所）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import json
import re

# ─── 定数 ────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SUBDIRS = ["pipelines", "jobs", "slack", "gws", "data", "rss", "ai", "setup", "utils", "lib"]
EXCLUDE_DIRS = {"old", "tests", "__pycache__", ".pytest_cache", ".venv"}
EXCLUDE_FILES = {"__init__.py", "conftest.py"}

# OS依存CLIコマンド（platform-commands.sh に集約すべきもの）
OS_DEPENDENT_COMMANDS = [
    # macOS固有
    "caffeinate",
    "launchctl",
    "pmset",
    "lsof",
    "pbcopy",
    "pbpaste",
    "open",       # macOS の open コマンド（xdg-open と異なる）
    "say",
    "defaults",
    "diskutil",
    "sw_vers",
    "networksetup",
    "dscl",
    "plutil",
    "hdiutil",
    # Linux固有
    "systemctl",
    "systemd-inhibit",
    "journalctl",
    "ss",         # socket statistics（lsof代替）
    "fuser",
    "xdg-open",
    "notify-send",
    "timedatectl",
]

# date コマンドはOS間で構文が異なる（-v vs -d）
# subprocess経由で呼ばれている場合のみ検出対象
DATE_COMMAND_PATTERNS = [
    re.compile(r'["\']date["\']'),
    re.compile(r'\["date"'),
    re.compile(r"date\s+-[vd]"),
]

# 許可リスト: platform-commands.sh 経由で呼んでいるファイル
# （PLATFORM_CMD を参照しているファイルは検出対象外）
PLATFORM_CMD_MARKER = re.compile(r"PLATFORM_CMD|platform.commands\.sh|platform-commands")

# subprocess呼び出しパターン
SUBPROCESS_PATTERNS = [
    re.compile(r"subprocess\.\w+\("),
    re.compile(r"os\.system\("),
    re.compile(r"os\.popen\("),
    re.compile(r"os\.exec"),
]


# ─── チェックロジック ─────────────────────────────────────────────

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


def check_file(file_path: Path, verbose: bool = False) -> list[dict]:
    """1ファイルをチェックし、違反箇所のリストを返す。"""
    violations: list[dict] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return violations

    # platform-commands.sh を参照しているファイルはスキップ
    # （正しく経由しているとみなす）
    if PLATFORM_CMD_MARKER.search(content):
        if verbose:
            rel = file_path.relative_to(SCRIPTS_DIR)
            print(f"  ⏭️  {rel} (platform-commands.sh 参照あり、スキップ)")
        return violations

    lines = content.splitlines()

    for line_no, line in enumerate(lines, start=1):
        # コメント行はスキップ
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        # OS依存コマンドの直接参照を検出
        for cmd in OS_DEPENDENT_COMMANDS:
            # 文字列リテラル内でコマンド名が使われているか
            # 単語境界で一致させる（部分一致を避ける）
            pattern = re.compile(
                rf'''(?:["']){cmd}(?:["'])'''
                rf"|"
                rf'''\[["']{cmd}["']'''
            )
            if pattern.search(line):
                # "open" は誤検出が多いので追加フィルタ
                if cmd == "open" and _is_python_open(line):
                    continue
                violations.append({
                    "file": str(file_path.relative_to(SCRIPTS_DIR)),
                    "line": line_no,
                    "command": cmd,
                    "content": line.strip(),
                })

        # date コマンドのOS依存構文
        for pattern in DATE_COMMAND_PATTERNS:
            if pattern.search(line):
                # subprocess 呼び出しのコンテキスト内かチェック
                if _in_subprocess_context(lines, line_no):
                    violations.append({
                        "file": str(file_path.relative_to(SCRIPTS_DIR)),
                        "line": line_no,
                        "command": "date (OS-dependent syntax)",
                        "content": line.strip(),
                    })
                    break

    return violations


def _is_python_open(line: str) -> bool:
    """Python組み込みのopen()関数かどうかを判定する。"""
    # open( で始まるか、= open( のパターン
    if re.search(r'\bopen\s*\(', line):
        return True
    # with open(...) パターン
    if "with open" in line:
        return True
    # Path(...).open() パターン
    if ".open(" in line:
        return True
    return False


def _in_subprocess_context(lines: list[str], target_line: int) -> bool:
    """対象行がsubprocess呼び出しのコンテキスト内かを簡易判定する。"""
    # 前後10行以内にsubprocess呼び出しがあるか
    start = max(0, target_line - 10)
    end = min(len(lines), target_line + 5)
    context = "\n".join(lines[start:end])
    for pattern in SUBPROCESS_PATTERNS:
        if pattern.search(context):
            return True
    return False


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OS依存コマンドの直接呼び出しを検出する"
    )
    parser.add_argument(
        "--dir", nargs="*",
        help="対象ディレクトリ（省略時: 全サブディレクトリ）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="スキップしたファイルも表示",
    )
    args = parser.parse_args()

    files = collect_files(args.dir)
    print(f"検証対象: {len(files)} ファイル\n")

    all_violations: list[dict] = []
    checked_count = 0

    for f in files:
        violations = check_file(f, verbose=args.verbose)
        checked_count += 1
        if violations:
            all_violations.extend(violations)
            for v in violations:
                print(f"  ❌ {v['file']}:{v['line']} — {v['command']}")
                print(f"     {v['content']}")
        elif args.verbose:
            rel = f.relative_to(SCRIPTS_DIR)
            if not PLATFORM_CMD_MARKER.search(
                f.read_text(encoding="utf-8", errors="replace")
            ):
                print(f"  ✅ {rel}")

    # サマリー
    print()
    print("=" * 50)
    if not all_violations:
        print(f"✅ 全 {checked_count} ファイル OK — OS依存コマンドの直接呼び出しなし")
        result = {"success": True, "checked": checked_count, "violations": []}
    else:
        print(f"❌ {len(all_violations)} 件の違反を検出:")
        print()
        print("  対処方法:")
        print("    1. platform-commands.sh に新しいコマンドを追加する")
        print("    2. Python から platform-commands.sh 経由で呼び出す")
        print("    3. Python標準ライブラリで代替する（推奨）")
        result = {
            "success": False,
            "checked": checked_count,
            "violations": all_violations,
        }

    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if not all_violations else 1)


if __name__ == "__main__":
    main()
