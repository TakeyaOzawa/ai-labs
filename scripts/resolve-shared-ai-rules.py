#!/usr/bin/env python3.12
"""
resolve-shared-ai-rules: ファイルパスに対応するルール/リファレンスを解決する

ファイルパスを引数に受け取り、該当するルール・リファレンスの
絶対パスを改行区切りで標準出力に出力する。
該当なしの場合は何も出力しない。

Usage:
    python3.12 ~/scripts/resolve-shared-ai-rules.py <file_path> [<file_path2> ...]
    python3.12 ~/scripts/resolve-shared-ai-rules.py "src/utils/helper.py"
    python3.12 ~/scripts/resolve-shared-ai-rules.py "tests/Unit/UserTest.php" "src/app.py"

例:
    python3.12 ~/scripts/resolve-shared-ai-rules.py "scripts/run-tech-pipeline.py"
    # 出力:
    # /Users/.../rules/contextual/python-coding-standards.md
    # /Users/.../.shared-ai/references/script-first-guide.md
    # /Users/.../.shared-ai/references/agent-pipeline-run-script-guide.md

出力: 改行区切りの絶対パス（該当なしなら空出力）
依存: 標準ライブラリのみ
"""

import json
import sys
from fnmatch import fnmatch
from pathlib import Path

HOME = Path.home()
SHARED_AI = HOME / ".shared-ai"

# ─── ルールマッピング定義 ────────────────────────────────────────────────

# (glob_pattern, target_path) のリスト
# 上から順に評価し、マッチした全てのターゲットを出力する（複数マッチあり）
RULES: list[tuple[str, Path]] = [
    ("**/*.py", SHARED_AI / "rules" / "contextual" / "python-coding-standards.md"),
    ("scripts/*.py", SHARED_AI / "references" / "script-first-guide.md"),
    ("**/scripts/run-*-pipeline.py", SHARED_AI / "references" / "agent-pipeline-run-script-guide.md"),
    ("**/*.sh", SHARED_AI / "rules" / "contextual" / "shell-coding-standards.md"),
    (".zshrc", SHARED_AI / "rules" / "contextual" / "env-sync.md"),
    (".bashrc", SHARED_AI / "rules" / "contextual" / "env-sync.md"),
    (".shared-ai/prompts/*.md", SHARED_AI / "references" / "prompt-editing-guide.md"),
    (".shared-ai/references/*-guide.md", SHARED_AI / "references" / "reference-format-guide.md"),
    ("tests/**/*Test.php", SHARED_AI / "rules" / "contextual" / "test-db-guard.md"),
    ("docs/domain/**/*.md", SHARED_AI / "rules" / "contextual" / "domain-frontmatter.md"),
    (".kiro/specs/**/*.md", SHARED_AI / "rules" / "contextual" / "spec-frontmatter.md"),
    (".kiro/specs/**/design.md", SHARED_AI / "references" / "spec-design-guide.md"),
    (".kiro/specs/**/requirements.md", SHARED_AI / "references" / "spec-requirements-guide.md"),
    (".kiro/specs/**/tasks.md", SHARED_AI / "references" / "spec-tasks-guide.md"),
    (".kiro/steering/*.md", SHARED_AI / "references" / "steering-reference-guide.md"),
    (".kiro/**/*.md", SHARED_AI / "references" / "ai-architecture-guide.md"),
    (".kiro/**/*.json", SHARED_AI / "references" / "ai-architecture-guide.md"),
    (".kiro/**/*.hook", SHARED_AI / "references" / "ai-architecture-guide.md"),
    ("works/poc-something/**/SUMMARY.md", SHARED_AI / "references" / "poc-writer-guide.md"),
    (".shared-ai/**/*.md", SHARED_AI / "references" / "shared-ai-directory-guide.md"),
    ("**/README.md", SHARED_AI / "rules" / "contextual" / "readme-guide.md"),
]


def normalize_path(file_path: str) -> str:
    """ファイルパスを正規化する。ホームディレクトリからの相対パスに変換。"""
    p = Path(file_path).expanduser()

    # 絶対パスの場合、ホームディレクトリからの相対パスに変換
    if p.is_absolute():
        try:
            return str(p.relative_to(HOME))
        except ValueError:
            return str(p)

    # 先頭の ~/ を除去
    path_str = str(p)
    if path_str.startswith("~/"):
        path_str = path_str[2:]

    return path_str


def match_pattern(pattern: str, file_path: str) -> bool:
    """globパターンとファイルパスをマッチングする。

    fnmatchは ** をサポートしないため、独自に処理する。
    """
    # ** を含むパターンの処理
    if "**" in pattern:
        # パターンを ** で分割
        parts = pattern.split("**")
        if len(parts) == 2:
            prefix = parts[0]  # ** の前
            suffix = parts[1]  # ** の後

            # prefix が空でない場合、ファイルパスがprefixで始まるか確認
            if prefix and not file_path.startswith(prefix):
                return False

            # suffix のマッチング（末尾部分）
            if suffix:
                # suffix が / で始まる場合は除去
                suffix_pattern = suffix.lstrip("/")
                # ファイルパスの各サブパスに対してsuffixをマッチ
                remaining = file_path[len(prefix):]
                # remaining の中で suffix_pattern にマッチする部分を探す
                path_parts = remaining.split("/")
                for i in range(len(path_parts)):
                    sub_path = "/".join(path_parts[i:])
                    if fnmatch(sub_path, suffix_pattern):
                        return True
                return False
            else:
                # suffix が空 = ** で終わるパターン → prefixで始まれば全マッチ
                return True

    # ** を含まない通常のglobパターン
    return fnmatch(file_path, pattern)


def resolve(file_path: str) -> list[str]:
    """ファイルパスに対応するルールパスのリストを返す。"""
    normalized = normalize_path(file_path)
    results: list[str] = []
    seen: set[str] = set()

    for pattern, target in RULES:
        if match_pattern(pattern, normalized):
            target_str = str(target)
            if target_str not in seen:
                seen.add(target_str)
                results.append(target_str)

    return results


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps({"success": False, "error": "ファイルパスが指定されていません"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(2)

    all_results: list[str] = []
    seen: set[str] = set()

    for file_path in sys.argv[1:]:
        for result in resolve(file_path):
            if result not in seen:
                seen.add(result)
                all_results.append(result)

    # 改行区切りで出力（該当なしなら何も出力しない）
    if all_results:
        print("\n".join(all_results))


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
