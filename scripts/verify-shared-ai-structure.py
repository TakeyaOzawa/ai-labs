#!/usr/bin/env python3.12
"""
verify-shared-ai-structure: .shared-ai 階層構造の整合性を検証する

以下を検証する:
1. rules/critical/, rules/quality/, rules/直下のdispatcher存在確認
2. 全steeringファイルのreadFile参照先パスが実在するか
3. resolve-shared-ai-rules.py の全パターンマッチテスト
4. setup-symlinks.py --verify の実行
5. 旧パス（rules/always/, rules/contextual/）への参照がないことをgrep確認
6. claude / kiro-cli 両方でdispatcherが正しく読み込まれるか検証

Usage:
    python3.12 ~/scripts/verify-shared-ai-structure.py
    python3.12 ~/scripts/verify-shared-ai-structure.py --verbose
    python3.12 ~/scripts/verify-shared-ai-structure.py --check structure
    python3.12 ~/scripts/verify-shared-ai-structure.py --check steering
    python3.12 ~/scripts/verify-shared-ai-structure.py --check resolve
    python3.12 ~/scripts/verify-shared-ai-structure.py --check symlinks
    python3.12 ~/scripts/verify-shared-ai-structure.py --check legacy
    python3.12 ~/scripts/verify-shared-ai-structure.py --check dispatcher

依存: 標準ライブラリのみ（+ 同ディレクトリの resolve-shared-ai-rules.py, ai-command-builder.py）
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SHARED_AI = HOME / ".shared-ai"
SCRIPTS_DIR = Path(__file__).parent
STEERING_DIR = HOME / ".kiro" / "steering"

# ─── 検証結果 ────────────────────────────────────────────────────

class VerifyResult:
    """検証結果を蓄積するクラス。"""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.warnings: int = 0
        self.details: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed += 1
        self.details.append(f"  ✓ {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        self.details.append(f"  ✗ {msg}")

    def warn(self, msg: str) -> None:
        self.warnings += 1
        self.details.append(f"  ⚠ {msg}")

    @property
    def success(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        status = "✅ PASS" if self.success else "❌ FAIL"
        return f"{status} (passed={self.passed}, failed={self.failed}, warnings={self.warnings})"


# ─── Check 1: ディレクトリ構造 ───────────────────────────────────

def check_structure(verbose: bool) -> VerifyResult:
    """rules/ の構造が正しいか検証する。"""
    result = VerifyResult()
    print("\n[1] ディレクトリ構造検証")

    # dispatcher が rules/ 直下に存在すること
    for name in ("filematch-dispatcher.md", "command-dispatcher.md"):
        path = SHARED_AI / "rules" / name
        if path.exists():
            result.ok(f"rules/{name} 存在")
        else:
            result.fail(f"rules/{name} が存在しない")

    # critical/ ディレクトリとその中身
    critical_dir = SHARED_AI / "rules" / "critical"
    expected_critical = [
        "dev-environment.md",
        "test-db-guard.md",
        "env-sync.md",
        "spec-frontmatter.md",
        "domain-frontmatter.md",
    ]
    if critical_dir.is_dir():
        result.ok("rules/critical/ ディレクトリ存在")
        for name in expected_critical:
            if (critical_dir / name).exists():
                result.ok(f"rules/critical/{name} 存在")
            else:
                result.fail(f"rules/critical/{name} が存在しない")
    else:
        result.fail("rules/critical/ ディレクトリが存在しない")

    # quality/ ディレクトリとその中身
    quality_dir = SHARED_AI / "rules" / "quality"
    expected_quality = [
        "python-coding-standards.md",
        "shell-coding-standards.md",
        "readme-guide.md",
        "pr-creation.md",
        "gws-integration.md",
    ]
    if quality_dir.is_dir():
        result.ok("rules/quality/ ディレクトリ存在")
        for name in expected_quality:
            if (quality_dir / name).exists():
                result.ok(f"rules/quality/{name} 存在")
            else:
                result.fail(f"rules/quality/{name} が存在しない")
    else:
        result.fail("rules/quality/ ディレクトリが存在しない")

    # 旧ディレクトリが存在しないこと
    for old_dir in ("always", "contextual"):
        old_path = SHARED_AI / "rules" / old_dir
        if old_path.exists():
            result.fail(f"旧ディレクトリ rules/{old_dir}/ が残存")
        else:
            result.ok(f"旧ディレクトリ rules/{old_dir}/ なし")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 2: steering readFile参照先 ───────────────────────────

def check_steering(verbose: bool) -> VerifyResult:
    """全steeringファイルのreadFile参照先が実在するか検証する。"""
    result = VerifyResult()
    print("\n[2] steering readFile参照先検証")

    if not STEERING_DIR.is_dir():
        result.fail(f"steering ディレクトリが存在しない: {STEERING_DIR}")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # readFile参照パターン: `~/.shared-ai/...` or `~/scripts/...`
    ref_pattern = re.compile(r"`(~/[^`]+)`")

    for md_file in sorted(STEERING_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        refs = ref_pattern.findall(content)

        if not refs:
            if verbose:
                result.ok(f"{md_file.name}: 参照なし（スキップ）")
            continue

        for ref in refs:
            # ~ を展開
            expanded = Path(ref.replace("~", str(HOME)))
            if expanded.exists():
                result.ok(f"{md_file.name}: {ref} → 存在")
            else:
                result.fail(f"{md_file.name}: {ref} → 存在しない")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 3: resolve-shared-ai-rules.py パターンマッチ ─────────

def check_resolve(verbose: bool) -> VerifyResult:
    """resolve-shared-ai-rules.py の全パターンが正しく解決されるか検証する。"""
    result = VerifyResult()
    print("\n[3] resolve-shared-ai-rules.py パターンマッチ検証")

    resolve_script = SCRIPTS_DIR / "resolve-shared-ai-rules.py"
    if not resolve_script.exists():
        result.fail(f"resolve-shared-ai-rules.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # テストケース: (入力パス, 期待される出力パスの部分文字列リスト)
    test_cases: list[tuple[str, list[str]]] = [
        ("src/app.py", ["python-coding-standards.md"]),
        ("scripts/run-daily-pipeline.py", [
            "python-coding-standards.md",
            "script-first-guide.md",
            "agent-pipeline-run-script-guide.md",
        ]),
        ("scripts/check-env.py", [
            "python-coding-standards.md",
            "script-first-guide.md",
        ]),
        ("deploy.sh", ["shell-coding-standards.md"]),
        (".zshrc", ["env-sync.md"]),
        ("tests/Unit/UserTest.php", ["test-db-guard.md"]),
        ("docs/domain/sales/overview.md", ["domain-frontmatter.md"]),
        (".kiro/specs/feature/tasks.md", [
            "spec-frontmatter.md",
            "spec-tasks-guide.md",
        ]),
        (".kiro/steering/my-rule.md", ["steering-reference-guide.md"]),
        ("README.md", ["readme-guide.md"]),
        (".shared-ai/rules/critical/new-rule.md", ["shared-ai-directory-guide.md"]),
    ]

    for input_path, expected_fragments in test_cases:
        proc = subprocess.run(
            ["python3.12", str(resolve_script), input_path],
            capture_output=True, text=True,
        )
        output = proc.stdout.strip()
        output_lines = output.splitlines() if output else []

        all_found = True
        for fragment in expected_fragments:
            if any(fragment in line for line in output_lines):
                if verbose:
                    result.ok(f"{input_path} → {fragment}")
            else:
                result.fail(f"{input_path} → {fragment} が出力に含まれない")
                all_found = False

        if all_found and not verbose:
            result.ok(f"{input_path} → 全{len(expected_fragments)}件マッチ")

        # 出力されたパスが全て実在するか確認
        for line in output_lines:
            path = Path(line.strip())
            if not path.exists():
                result.fail(f"{input_path}: 解決先が存在しない: {line.strip()}")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 4: setup-symlinks.py --verify ────────────────────────

def check_symlinks(verbose: bool) -> VerifyResult:
    """setup-symlinks.py --verify を実行する。"""
    result = VerifyResult()
    print("\n[4] symlink検証 (setup-symlinks.py --verify)")

    symlink_script = SCRIPTS_DIR / "setup-symlinks.py"
    if not symlink_script.exists():
        result.fail("setup-symlinks.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    proc = subprocess.run(
        ["python3.12", str(symlink_script), "--verify"],
        capture_output=True, text=True,
    )

    if proc.returncode == 0:
        result.ok("setup-symlinks.py --verify: 全symlink正常")
    else:
        result.fail("setup-symlinks.py --verify: 問題あり")

    if verbose or proc.returncode != 0:
        for line in proc.stdout.splitlines():
            print(f"    {line}")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 5: 旧パス参照の残存チェック ──────────────────────────

def check_legacy(verbose: bool) -> VerifyResult:
    """旧パス（rules/always/, rules/contextual/）への参照が残っていないか確認する。"""
    result = VerifyResult()
    print("\n[5] 旧パス参照の残存チェック")

    # 検索対象ディレクトリ
    search_dirs = [
        HOME / ".shared-ai",
        HOME / ".kiro",
        HOME / "scripts",
        HOME / ".claude",
        HOME / ".gemini",
        HOME / ".codex",
    ]

    legacy_patterns = [
        "rules/always/",
        "rules/contextual/",
    ]

    # 自身のスクリプトは除外（チェック対象文字列をリテラルとして含むため）
    self_path = str(Path(__file__).resolve())

    found_any = False
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        for pattern in legacy_patterns:
            proc = subprocess.run(
                ["grep", "-r", "--include=*.md", "--include=*.py",
                 "--include=*.json", "-l", pattern, str(search_dir)],
                capture_output=True, text=True,
            )
            if proc.stdout.strip():
                for file_path in proc.stdout.strip().splitlines():
                    # __pycache__ を除外
                    if "__pycache__" in file_path:
                        continue
                    # issues/ 配下は除外（計画ドキュメント）
                    if "/issues/" in file_path:
                        continue
                    # 自分自身を除外
                    if Path(file_path).resolve() == Path(self_path):
                        continue
                    result.fail(f"旧パス参照残存: {file_path} ({pattern})")
                    found_any = True

    if not found_any:
        result.ok("旧パス（rules/always/, rules/contextual/）への参照なし")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 6: dispatcher コマンド構築検証 ────────────────────────

def check_dispatcher(verbose: bool) -> VerifyResult:
    """claude / kiro-cli 両方でdispatcherが正しくコマンド構築されるか検証する。"""
    result = VerifyResult()
    print("\n[6] dispatcher コマンド構築検証 (ai-command-builder.py)")

    # ai-command-builder.py を import
    builder_script = SCRIPTS_DIR / "ai-command-builder.py"
    if not builder_script.exists():
        result.fail("ai-command-builder.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # import via importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai_command_builder", builder_script)
    if spec is None or spec.loader is None:
        result.fail("ai-command-builder.py の読み込みに失敗")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    test_prompt = "テストプロンプト"
    test_agent = "test-agent"

    # claude タイプ
    cmd = mod.build_ai_command(test_prompt, ai_type="claude", agent_name=test_agent)
    if cmd[0] == "claude" and "--print" in cmd and test_agent in cmd:
        result.ok("claude コマンド構築: 正常")
        if verbose:
            print(f"    cmd: {cmd}")
    else:
        result.fail(f"claude コマンド構築: 不正 → {cmd}")

    # claude タイプ（エージェントなし）
    cmd = mod.build_ai_command(test_prompt, ai_type="claude")
    if cmd[0] == "claude" and "--agent" not in cmd and test_prompt in cmd:
        result.ok("claude コマンド構築（エージェントなし）: 正常")
    else:
        result.fail(f"claude コマンド構築（エージェントなし）: 不正 → {cmd}")

    # claude タイプ（interactive）
    cmd = mod.build_ai_command(test_prompt, ai_type="claude", interactive=True)
    if cmd[0] == "claude" and "--print" not in cmd and "--dangerously-skip-permissions" in cmd:
        result.ok("claude コマンド構築（interactive）: 正常")
    else:
        result.fail(f"claude コマンド構築（interactive）: 不正 → {cmd}")

    # kiro-cli タイプ
    cmd = mod.build_ai_command(test_prompt, ai_type="kiro-cli", agent_name=test_agent)
    if cmd[0] == "kiro-cli" and "--no-interactive" in cmd and test_agent in cmd:
        result.ok("kiro-cli コマンド構築: 正常")
        if verbose:
            print(f"    cmd: {cmd}")
    else:
        result.fail(f"kiro-cli コマンド構築: 不正 → {cmd}")

    # kiro-cli タイプ（interactive）
    cmd = mod.build_ai_command(test_prompt, ai_type="kiro-cli", interactive=True)
    if cmd[0] == "kiro-cli" and "--no-interactive" not in cmd:
        result.ok("kiro-cli コマンド構築（interactive）: 正常")
    else:
        result.fail(f"kiro-cli コマンド構築（interactive）: 不正 → {cmd}")

    # 不正タイプ
    try:
        mod.build_ai_command(test_prompt, ai_type="invalid")
        result.fail("不正タイプで ValueError が発生しない")
    except ValueError:
        result.ok("不正タイプで ValueError 発生: 正常")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── メイン ──────────────────────────────────────────────────────

ALL_CHECKS = {
    "structure": check_structure,
    "steering": check_steering,
    "resolve": check_resolve,
    "symlinks": check_symlinks,
    "legacy": check_legacy,
    "dispatcher": check_dispatcher,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=".shared-ai 階層構造の整合性を検証する",
    )
    parser.add_argument(
        "--check", choices=list(ALL_CHECKS.keys()), default=None,
        help="特定のチェックのみ実行（省略時: 全チェック）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="詳細出力",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  verify-shared-ai-structure: 階層構造整合性検証")
    print("=" * 60)

    if args.check:
        checks = {args.check: ALL_CHECKS[args.check]}
    else:
        checks = ALL_CHECKS

    results: list[VerifyResult] = []
    for name, check_fn in checks.items():
        r = check_fn(args.verbose)
        results.append(r)

    # 総合結果
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_warnings = sum(r.warnings for r in results)

    print("\n" + "=" * 60)
    if total_failed == 0:
        print(f"  ✅ 全チェック PASS (passed={total_passed}, warnings={total_warnings})")
        sys.exit(0)
    else:
        print(f"  ❌ 検証失敗 (passed={total_passed}, failed={total_failed}, warnings={total_warnings})")
        sys.exit(1)


from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
