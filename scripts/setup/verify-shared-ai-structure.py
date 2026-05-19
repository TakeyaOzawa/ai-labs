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
7. steering fileMatch と resolve-shared-ai-rules.py の出力整合性検証
8. command-dispatcher.md 内の参照先パス実在検証
9. AI設定ファイル（CLAUDE.md, GEMINI.md, AGENTS.md）の参照先パス実在検証

Usage:
    python3.12 ~/scripts/verify-shared-ai-structure.py
    python3.12 ~/scripts/verify-shared-ai-structure.py --quick
    python3.12 ~/scripts/verify-shared-ai-structure.py --verbose
    python3.12 ~/scripts/verify-shared-ai-structure.py --check structure
    python3.12 ~/scripts/verify-shared-ai-structure.py --check steering
    python3.12 ~/scripts/verify-shared-ai-structure.py --check resolve
    python3.12 ~/scripts/verify-shared-ai-structure.py --check symlinks
    python3.12 ~/scripts/verify-shared-ai-structure.py --check legacy
    python3.12 ~/scripts/verify-shared-ai-structure.py --check dispatcher
    python3.12 ~/scripts/verify-shared-ai-structure.py --check consistency
    python3.12 ~/scripts/verify-shared-ai-structure.py --check command-dispatcher
    python3.12 ~/scripts/verify-shared-ai-structure.py --check ai-config

依存: 標準ライブラリのみ（+ 同ディレクトリの resolve-shared-ai-rules.py, ai-cli-utils.py）
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import re
import subprocess

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

    # dispatcher が rules/ 直下に存在すること（双方向チェック）
    rules_dir = SHARED_AI / "rules"
    expected_dispatchers = {
        "filematch-dispatcher.md",
        "command-dispatcher.md",
    }
    actual_dispatchers = {f.name for f in rules_dir.glob("*.md")}
    for name in sorted(expected_dispatchers - actual_dispatchers):
        result.fail(
            f"rules/{name} が存在しない"
            f"（ファイル削除済みなら expected_dispatchers から削除してください）"
        )
    for name in sorted(actual_dispatchers - expected_dispatchers):
        result.fail(
            f"rules/{name} が expected_dispatchers に未登録"
            f"（expected_dispatchers に追記してください）"
        )
    for name in sorted(expected_dispatchers & actual_dispatchers):
        result.ok(f"rules/{name} 存在")

    # critical/ ディレクトリとその中身（双方向チェック）
    critical_dir = SHARED_AI / "rules" / "critical"
    expected_critical = {
        "dev-environment.md",
        "test-db-guard.md",
        "env-sync.md",
        "spec-frontmatter.md",
        "domain-frontmatter.md",
    }
    if critical_dir.is_dir():
        result.ok("rules/critical/ ディレクトリ存在")
        actual_critical = {f.name for f in critical_dir.glob("*.md")}
        # リストにあるが実ファイルがない → 削除されたのにリスト未更新
        for name in sorted(expected_critical - actual_critical):
            result.fail(
                f"rules/critical/{name} が存在しない"
                f"（ファイル削除済みなら expected_critical から削除してください）"
            )
        # 実ファイルがあるがリストにない → 追加されたのにリスト未更新
        for name in sorted(actual_critical - expected_critical):
            result.fail(
                f"rules/critical/{name} が expected_critical に未登録"
                f"（expected_critical に追記してください）"
            )
        # 両方に存在するもの
        for name in sorted(expected_critical & actual_critical):
            result.ok(f"rules/critical/{name} 存在")
    else:
        result.fail("rules/critical/ ディレクトリが存在しない")

    # quality/ ディレクトリとその中身（双方向チェック）
    quality_dir = SHARED_AI / "rules" / "quality"
    expected_quality = {
        "python-coding-standards.md",
        "shell-coding-standards.md",
        "readme-guide.md",
        "pr-creation.md",
        "gws-integration.md",
    }
    if quality_dir.is_dir():
        result.ok("rules/quality/ ディレクトリ存在")
        actual_quality = {f.name for f in quality_dir.glob("*.md")}
        # リストにあるが実ファイルがない → 削除されたのにリスト未更新
        for name in sorted(expected_quality - actual_quality):
            result.fail(
                f"rules/quality/{name} が存在しない"
                f"（ファイル削除済みなら expected_quality から削除してください）"
            )
        # 実ファイルがあるがリストにない → 追加されたのにリスト未更新
        for name in sorted(actual_quality - expected_quality):
            result.fail(
                f"rules/quality/{name} が expected_quality に未登録"
                f"（expected_quality に追記してください）"
            )
        # 両方に存在するもの
        for name in sorted(expected_quality & actual_quality):
            result.ok(f"rules/quality/{name} 存在")
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

    resolve_script = SCRIPTS_DIR.parent / "ai" / "resolve-shared-ai-rules.py"
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
    print("\n[6] dispatcher コマンド構築検証 (ai-cli-utils.py)")

    # ai-cli-utils.py を import
    builder_script = SCRIPTS_DIR.parent / "ai" / "ai-cli-utils.py"
    if not builder_script.exists():
        result.fail("ai-cli-utils.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # import via importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai_cli_utils", builder_script)
    if spec is None or spec.loader is None:
        result.fail("ai-cli-utils.py の読み込みに失敗")
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


# ─── Check 7: steering fileMatch ↔ resolve 整合性 ───────────────

def check_steering_resolve_consistency(verbose: bool) -> VerifyResult:
    """steering の fileMatchPattern と resolve-shared-ai-rules.py の出力が整合するか検証する。

    「あるファイルパスに対して steering が発火するルール」と
    「resolve-shared-ai-rules.py が返すルール」が一致することを確認する。
    これにより、Kiro 環境と非 Kiro 環境（claude 等）で同じルールが適用されることを保証する。
    """
    result = VerifyResult()
    print("\n[7] steering fileMatch ↔ resolve 整合性検証")

    resolve_script = SCRIPTS_DIR.parent / "ai" / "resolve-shared-ai-rules.py"
    if not resolve_script.exists():
        result.fail("resolve-shared-ai-rules.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    if not STEERING_DIR.is_dir():
        result.fail(f"steering ディレクトリが存在しない: {STEERING_DIR}")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # テストケース: (入力ファイルパス, 発火すべきsteering, steeringが参照するルールパスの部分文字列)
    # steering の fileMatchPattern に基づいて、resolve の出力にも同じルールが含まれるか確認
    test_cases: list[tuple[str, str, str]] = [
        # env-sync.md: **/.zshrc, **/.bashrc, .shared-ai/prompts/*.md
        (".zshrc", "env-sync.md", "rules/critical/env-sync.md"),
        (".bashrc", "env-sync.md", "rules/critical/env-sync.md"),
        # py-standards.md: **/*.py
        ("scripts/check-env.py", "py-standards.md", "rules/quality/python-coding-standards.md"),
        # sh-standards.md: **/*.sh
        ("deploy.sh", "sh-standards.md", "rules/quality/shell-coding-standards.md"),
        # pipeline-run-script.md: **/scripts/run-*-pipeline.py
        ("scripts/run-daily-pipeline.py", "pipeline-run-script.md", "agent-pipeline-run-script-guide.md"),
        # script-first-rule.md: scripts/*.py, .shared-ai/prompts/*.md
        ("scripts/check-env.py", "script-first-rule.md", "references/script-first-guide.md"),
        # test-db-guard.md: tests/**/*Test.php
        ("tests/Unit/UserTest.php", "test-db-guard.md", "rules/critical/test-db-guard.md"),
        # domain-frontmatter.md: docs/domain/**/*.md
        ("docs/domain/sales/overview.md", "domain-frontmatter.md", "rules/critical/domain-frontmatter.md"),
        # spec-frontmatter.md: .kiro/specs/**/*.md
        (".kiro/specs/feature/tasks.md", "spec-frontmatter.md", "rules/critical/spec-frontmatter.md"),
        # design-format.md: .kiro/specs/**/design.md
        (".kiro/specs/feature/design.md", "design-format.md", "references/spec-design-guide.md"),
        # req-format.md: .kiro/specs/**/requirements.md
        (".kiro/specs/feature/requirements.md", "req-format.md", "references/spec-requirements-guide.md"),
        # tasks-format.md: .kiro/specs/**/tasks.md
        (".kiro/specs/feature/tasks.md", "tasks-format.md", "references/spec-tasks-guide.md"),
        # steering-ref.md: .kiro/steering/*.md
        (".kiro/steering/my-rule.md", "steering-ref.md", "references/steering-reference-guide.md"),
        # kiro-arch.md: .kiro/**/*.md, .kiro/**/*.json, .kiro/**/*.hook
        (".kiro/agents/my-agent.json", "kiro-arch.md", "references/ai-architecture-guide.md"),
        # prompt-editing.md: .shared-ai/prompts/*.md
        (".shared-ai/prompts/my-prompt.md", "prompt-editing.md", "references/prompt-editing-guide.md"),
        # ref-format.md: .shared-ai/references/*-guide.md
        (".shared-ai/references/new-guide.md", "ref-format.md", "references/reference-format-guide.md"),
        # poc-writer.md: works/poc-something/**/SUMMARY.md
        ("works/poc-something/v1/SUMMARY.md", "poc-writer.md", "references/poc-writer-guide.md"),
        # README.md → dispatcher経由（fileMatch steering なし）
        ("README.md", "(dispatcher)", "rules/quality/readme-guide.md"),
    ]

    # readFile参照パターン
    ref_pattern = re.compile(r"`(~/[^`]+)`")

    for input_path, expected_steering, expected_rule_fragment in test_cases:
        # 1. resolve-shared-ai-rules.py の出力を確認
        proc = subprocess.run(
            ["python3.12", str(resolve_script), input_path],
            capture_output=True, text=True,
        )
        resolve_output = proc.stdout.strip().splitlines() if proc.stdout.strip() else []

        resolve_has_rule = any(expected_rule_fragment in line for line in resolve_output)

        # 2. steering の fileMatchPattern 確認（dispatcher 経由のものはスキップ）
        if expected_steering == "(dispatcher)":
            # dispatcher 経由でのみ到達するケース: resolve の出力のみ確認
            if resolve_has_rule:
                result.ok(f"{input_path} → resolve: {expected_rule_fragment} ✓ (dispatcher経由)")
            else:
                result.fail(f"{input_path} → resolve に {expected_rule_fragment} が含まれない")
            continue

        # steering ファイルの readFile 参照先を取得
        steering_file = STEERING_DIR / expected_steering
        if not steering_file.exists():
            result.fail(f"{input_path} → steering {expected_steering} が存在しない")
            continue

        steering_content = steering_file.read_text(encoding="utf-8")
        steering_refs = ref_pattern.findall(steering_content)
        steering_has_rule = any(expected_rule_fragment in ref for ref in steering_refs)

        # 3. 両方が同じルールを指しているか確認
        if steering_has_rule and resolve_has_rule:
            result.ok(f"{input_path} → steering({expected_steering}) + resolve 両方一致: {expected_rule_fragment}")
        elif steering_has_rule and not resolve_has_rule:
            result.fail(f"{input_path} → steering は {expected_rule_fragment} を参照するが resolve に含まれない")
        elif not steering_has_rule and resolve_has_rule:
            result.fail(f"{input_path} → resolve は {expected_rule_fragment} を返すが steering({expected_steering}) に含まれない")
        else:
            result.fail(f"{input_path} → steering/resolve 両方に {expected_rule_fragment} が見つからない")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 8: command-dispatcher 参照先検証 ──────────────────────

def check_command_dispatcher(verbose: bool) -> VerifyResult:
    """command-dispatcher.md 内のreadFile対象パスが全て実在するか検証する。

    command-dispatcher は「操作の種類」に応じてルールを読み込む仕組みで、
    ファイルパスベースの fileMatch とは異なる。テーブル内の全参照先が
    実在することを確認する。
    """
    result = VerifyResult()
    print("\n[8] command-dispatcher 参照先検証")

    cmd_dispatcher = SHARED_AI / "rules" / "command-dispatcher.md"
    if not cmd_dispatcher.exists():
        result.fail("command-dispatcher.md が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    content = cmd_dispatcher.read_text(encoding="utf-8")

    # テーブル内の `~/...` パスを全て抽出
    ref_pattern = re.compile(r"`(~/[^`]+)`")
    refs = ref_pattern.findall(content)

    if not refs:
        result.fail("command-dispatcher.md 内に readFile 参照が見つからない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    for ref in refs:
        expanded = Path(ref.replace("~", str(HOME)))
        if expanded.exists():
            result.ok(f"{ref} → 存在")
        else:
            result.fail(f"{ref} → 存在しない")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 9: AI設定ファイル参照先検証 ───────────────────────────

def check_ai_config_refs(verbose: bool) -> VerifyResult:
    """各AIツールの設定ファイル内のreadFile参照先が実在するか検証する。

    .claude/CLAUDE.md, .gemini/GEMINI.md, .codex/AGENTS.md 内の
    `~/...` パス参照が全て実在することを確認する。
    """
    result = VerifyResult()
    print("\n[9] AI設定ファイル参照先検証")

    # 検証対象ファイル
    config_files = [
        HOME / ".claude" / "CLAUDE.md",
        HOME / ".gemini" / "GEMINI.md",
        HOME / ".codex" / "AGENTS.md",
    ]

    ref_pattern = re.compile(r"`(~/[^`]+)`")

    for config_file in config_files:
        if not config_file.exists():
            if verbose:
                result.warn(f"{config_file.name}: ファイルが存在しない（スキップ）")
            continue

        content = config_file.read_text(encoding="utf-8")
        refs = ref_pattern.findall(content)

        if not refs:
            if verbose:
                result.ok(f"{config_file.name}: 参照なし（スキップ）")
            continue

        for ref in refs:
            expanded = Path(ref.replace("~", str(HOME)))
            if expanded.exists():
                result.ok(f"{config_file.name}: {ref} → 存在")
            else:
                result.fail(f"{config_file.name}: {ref} → 存在しない")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── メイン ──────────────────────────────────────────────────────

# チェック分類: quick = 軽量（静的検証のみ）、full = 重量（外部プロセス実行を含む）
QUICK_CHECKS = {
    "structure": check_structure,
    "steering": check_steering,
    "legacy": check_legacy,
    "command-dispatcher": check_command_dispatcher,
    "ai-config": check_ai_config_refs,
}

FULL_CHECKS = {
    "resolve": check_resolve,
    "symlinks": check_symlinks,
    "dispatcher": check_dispatcher,
    "consistency": check_steering_resolve_consistency,
}

ALL_CHECKS = {**QUICK_CHECKS, **FULL_CHECKS}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=".shared-ai 階層構造の整合性を検証する",
    )
    parser.add_argument(
        "--check", choices=list(ALL_CHECKS.keys()), default=None,
        help="特定のチェックのみ実行（省略時: 全チェック）",
    )
    parser.add_argument(
        "--quick", "-q", action="store_true",
        help="軽量チェックのみ実行（外部プロセス実行を伴うチェックをスキップ）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="詳細出力",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  verify-shared-ai-structure: 階層構造整合性検証")
    if args.quick:
        print("  (--quick: 軽量チェックのみ)")
    print("=" * 60)

    if args.check:
        checks = {args.check: ALL_CHECKS[args.check]}
    elif args.quick:
        checks = QUICK_CHECKS
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



if __name__ == "__main__":
    main()
