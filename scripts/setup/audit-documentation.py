#!/usr/bin/env python3.12
"""
audit-documentation: README/ドキュメントの整合性を自動チェックする

以下を検証する:
1. README内のMarkdownリンク先ファイルの実在確認
2. steering対応表と実ファイルの双方向チェック
3. agents-prompts 1:1対応チェック
4. scripts/README.md のスクリプト一覧と実ファイルの差分検出
5. interfaces/ の命名規則チェック
6. symlink定義とREADMEテーブルの整合性チェック
7. resolve-shared-ai-rules.py のターゲット実在確認

Usage:
    python3.12 ~/scripts/audit-documentation.py
    python3.12 ~/scripts/audit-documentation.py --check links
    python3.12 ~/scripts/audit-documentation.py --check steering
    python3.12 ~/scripts/audit-documentation.py --check agents
    python3.12 ~/scripts/audit-documentation.py --check scripts
    python3.12 ~/scripts/audit-documentation.py --check interfaces
    python3.12 ~/scripts/audit-documentation.py --check symlinks
    python3.12 ~/scripts/audit-documentation.py --check resolve
    python3.12 ~/scripts/audit-documentation.py --verbose

出力: チェック結果サマリー（PASS/FAIL）
依存: 標準ライブラリのみ
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import json
import re

HOME = Path.home()
SHARED_AI = HOME / ".shared-ai"
SCRIPTS_DIR = Path(__file__).parent
STEERING_DIR = HOME / ".kiro" / "steering"
AGENTS_DIR = HOME / ".kiro" / "agents"
PROMPTS_DIR = SHARED_AI / "prompts"
INTERFACES_DIR = SHARED_AI / "interfaces"


# ─── 検証結果 ────────────────────────────────────────────────────

class AuditResult:
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


# ─── Check 1: README内リンク先の実在確認 ─────────────────────────

def check_links(verbose: bool) -> AuditResult:
    """README.md内のMarkdownリンク先ファイルが実在するか検証する。"""
    result = AuditResult()
    print("\n[1] README内リンク先の実在確認")

    # チェック対象のREADMEファイル
    readme_files = [
        HOME / "README.md",
        SHARED_AI / "README.md",
        SCRIPTS_DIR / "README.md",
    ]

    # Markdownリンクパターン: [text](path)
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

    for readme in readme_files:
        if not readme.exists():
            result.warn(f"{readme.name}: ファイルが存在しない（スキップ）")
            continue

        content = readme.read_text(encoding="utf-8")
        links = link_pattern.findall(content)
        readme_dir = readme.parent

        for text, href in links:
            # 外部URL、アンカーリンク、プロトコル付きはスキップ
            if href.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # 相対パスを解決
            target = (readme_dir / href).resolve()

            if target.exists():
                if verbose:
                    result.ok(f"{readme.name}: [{text}]({href}) → 存在")
            else:
                result.fail(f"{readme.name}: [{text}]({href}) → 存在しない")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 2: steering対応表と実ファイルの双方向チェック ─────────

def check_steering(verbose: bool) -> AuditResult:
    """steering対応表と実ファイルの双方向整合性を検証する。"""
    result = AuditResult()
    print("\n[2] steering対応表と実ファイルの双方向チェック")

    shared_ai_readme = SHARED_AI / "README.md"
    if not shared_ai_readme.exists():
        result.fail(".shared-ai/README.md が存在しない")
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

    # README内のsteering対応表からファイル名を抽出
    content = shared_ai_readme.read_text(encoding="utf-8")
    # テーブル行のパターン: | `filename.md` | ... |
    table_pattern = re.compile(r"\|\s*`([^`]+\.md)`\s*\|")
    documented_steerings: set[str] = set()

    for match in table_pattern.finditer(content):
        name = match.group(1)
        # steering名のみ抽出（本体ファイル名は除外）
        # steeringテーブルの最初のカラムがsteering名
        # 行全体を見て判断
        line_start = content.rfind("\n", 0, match.start()) + 1
        line = content[line_start:content.find("\n", match.end())]
        # テーブルの最初のセルかどうか判断
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if cells and f"`{name}`" == cells[0]:
            documented_steerings.add(name)

    # 実際のsteeringファイル一覧
    actual_steerings = {f.name for f in STEERING_DIR.glob("*.md")}

    # 双方向チェック
    # READMEにあるが実ファイルがない
    for name in sorted(documented_steerings - actual_steerings):
        result.fail(f"README記載あり・実ファイルなし: {name}")

    # 実ファイルがあるがREADMEにない
    for name in sorted(actual_steerings - documented_steerings):
        result.fail(f"実ファイルあり・README記載なし: {name}")

    # 両方に存在
    matched = documented_steerings & actual_steerings
    if verbose:
        for name in sorted(matched):
            result.ok(f"{name}: README・実ファイル両方に存在")
    else:
        result.ok(f"{len(matched)}件のsteering: README・実ファイル一致")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 3: agents-prompts 1:1対応チェック ─────────────────────

def check_agents(verbose: bool) -> AuditResult:
    """agents JSONとprompts mdの1:1対応を検証する。"""
    result = AuditResult()
    print("\n[3] agents-prompts 1:1対応チェック")

    if not AGENTS_DIR.is_dir():
        result.fail(f"agents ディレクトリが存在しない: {AGENTS_DIR}")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    if not PROMPTS_DIR.is_dir():
        result.fail(f"prompts ディレクトリが存在しない: {PROMPTS_DIR}")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # agent JSON一覧（.example除外）
    agent_names = {
        f.stem for f in AGENTS_DIR.glob("*.json")
        if not f.name.endswith(".example")
    }

    # prompt md一覧
    prompt_names = {f.stem for f in PROMPTS_DIR.glob("*.md")}

    # agentあり・promptなし
    for name in sorted(agent_names - prompt_names):
        result.fail(f"agent JSONあり・promptなし: {name}")

    # promptあり・agentなし
    for name in sorted(prompt_names - agent_names):
        result.fail(f"promptあり・agent JSONなし: {name}")

    # 両方に存在
    matched = agent_names & prompt_names
    if verbose:
        for name in sorted(matched):
            result.ok(f"{name}: agent・prompt両方に存在")
    else:
        result.ok(f"{len(matched)}件: agent・prompt 1:1対応")

    # agent JSONのpromptパスが正しいか確認
    for agent_file in sorted(AGENTS_DIR.glob("*.json")):
        if agent_file.name.endswith(".example"):
            continue
        try:
            data = json.loads(agent_file.read_text(encoding="utf-8"))
            prompt_path = data.get("prompt", "")
            if prompt_path.startswith("file://"):
                # 相対パス解決
                rel_path = prompt_path[len("file://"):]
                resolved = (AGENTS_DIR / rel_path).resolve()
                if resolved.exists():
                    if verbose:
                        result.ok(f"{agent_file.name}: prompt参照先 存在")
                else:
                    result.fail(f"{agent_file.name}: prompt参照先が存在しない → {resolved}")
        except (json.JSONDecodeError, KeyError):
            result.warn(f"{agent_file.name}: JSON解析エラー")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 4: scripts/README.md のスクリプト一覧チェック ─────────

def check_scripts(verbose: bool) -> AuditResult:
    """scripts/README.md に全スクリプトが記載されているか検証する。"""
    result = AuditResult()
    print("\n[4] scripts/README.md スクリプト一覧チェック")

    scripts_readme = SCRIPTS_DIR / "README.md"
    if not scripts_readme.exists():
        result.fail("scripts/README.md が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    readme_content = scripts_readme.read_text(encoding="utf-8")

    # 実際のスクリプトファイル一覧
    actual_scripts: set[str] = set()
    for ext in ("*.py", "*.sh"):
        for f in SCRIPTS_DIR.glob(ext):
            actual_scripts.add(f.name)

    # README内で言及されているスクリプト
    documented: set[str] = set()
    for name in actual_scripts:
        if name in readme_content:
            documented.add(name)

    # 未記載のスクリプト
    undocumented = actual_scripts - documented
    # 内部モジュール（_で始まる）は警告レベル
    for name in sorted(undocumented):
        if name.startswith("_"):
            result.warn(f"内部モジュール未記載: {name}")
        else:
            result.fail(f"スクリプト未記載: {name}")

    if verbose:
        for name in sorted(documented):
            result.ok(f"{name}: README記載あり")
    else:
        result.ok(f"{len(documented)}件のスクリプト: README記載あり")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 5: interfaces/ 命名規則チェック ───────────────────────

def check_interfaces(verbose: bool) -> AuditResult:
    """interfaces/ ディレクトリのファイル命名規則を検証する。"""
    result = AuditResult()
    print("\n[5] interfaces/ 命名規則チェック")

    if not INTERFACES_DIR.is_dir():
        result.fail(f"interfaces ディレクトリが存在しない: {INTERFACES_DIR}")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # 許容される命名パターン
    valid_patterns = [
        re.compile(r"^.+-output\.md$"),           # {agent-name}-output.md
        re.compile(r"^.+-resources\.md$"),         # {agent-name}-resources.md
        re.compile(r"^.+-schema\.md$"),            # {topic}-schema.md
        re.compile(r"^.+-report-format\.md$"),     # {pipeline}-report-format.md
        re.compile(r"^.+-format\.md$"),            # {topic}-format.md（汎用）
    ]

    for f in sorted(INTERFACES_DIR.glob("*.md")):
        matched = any(p.match(f.name) for p in valid_patterns)
        if matched:
            if verbose:
                result.ok(f"{f.name}: 命名規則準拠")
        else:
            result.warn(f"{f.name}: 命名規則外（{', '.join(p.pattern for p in valid_patterns)}）")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 6: symlink定義の整合性チェック ────────────────────────

def check_symlinks(verbose: bool) -> AuditResult:
    """setup-symlinks.py の定義とREADMEのsymlinkテーブルの整合性を検証する。"""
    result = AuditResult()
    print("\n[6] symlink定義の整合性チェック")

    readme = HOME / "README.md"
    symlink_script = SCRIPTS_DIR / "setup-symlinks.py"

    if not readme.exists():
        result.fail("~/README.md が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    if not symlink_script.exists():
        result.fail("setup-symlinks.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    # setup-symlinks.py からsymlink定義を抽出
    script_content = symlink_script.read_text(encoding="utf-8")
    readme_content = readme.read_text(encoding="utf-8")

    # スクリプト内の "link" パスを抽出
    link_pattern = re.compile(r'"link":\s*HOME\s*/\s*"([^"]+)"(?:\s*/\s*"([^"]+)")?(?:\s*/\s*"([^"]+)")?')
    script_links: set[str] = set()

    for match in link_pattern.finditer(script_content):
        parts = [p for p in match.groups() if p]
        link_path = "/".join(parts)
        script_links.add(link_path)

    # README内のsymlinkテーブルからパスを抽出
    # パターン: | `~/.xxx/yyy` | `~/.zzz/www` | ... |
    table_link_pattern = re.compile(r"\|\s*`~/\.([^`]+)`\s*\|")
    readme_links: set[str] = set()

    for match in table_link_pattern.finditer(readme_content):
        readme_links.add(match.group(1))

    # スクリプトにあるがREADMEにない
    for link in sorted(script_links):
        # README内で言及されているか（テーブル以外も含む）
        if link in readme_content or link.replace("/", "") in readme_content:
            if verbose:
                result.ok(f"symlink {link}: README記載あり")
        else:
            # 部分一致でチェック
            found = False
            for part in link.split("/"):
                if len(part) > 3 and part in readme_content:
                    found = True
                    break
            if not found:
                result.fail(f"symlink {link}: README記載なし")
            elif verbose:
                result.ok(f"symlink {link}: README内で言及あり")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── Check 7: resolve-shared-ai-rules.py ターゲット実在確認 ──────

def check_resolve(verbose: bool) -> AuditResult:
    """resolve-shared-ai-rules.py のRULESリスト内の全ターゲットパスが実在するか検証する。"""
    result = AuditResult()
    print("\n[7] resolve-shared-ai-rules.py ターゲット実在確認")

    resolve_script = SCRIPTS_DIR / "resolve-shared-ai-rules.py"
    if not resolve_script.exists():
        result.fail("resolve-shared-ai-rules.py が存在しない")
        for line in result.details:
            print(line)
        print(f"  → {result.summary()}")
        return result

    content = resolve_script.read_text(encoding="utf-8")

    # SHARED_AI / "xxx" / "yyy" / "zzz.md" パターンを抽出
    path_pattern = re.compile(
        r'SHARED_AI\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"'
    )

    targets_checked: set[str] = set()
    for match in path_pattern.finditer(content):
        parts = match.groups()
        target = SHARED_AI / parts[0] / parts[1] / parts[2]
        target_str = str(target)

        if target_str in targets_checked:
            continue
        targets_checked.add(target_str)

        if target.exists():
            if verbose:
                result.ok(f"{'/'.join(parts)}: 存在")
        else:
            result.fail(f"{'/'.join(parts)}: 存在しない")

    # 2階層パターン: SHARED_AI / "xxx" / "yyy.md"
    path_pattern_2 = re.compile(
        r'SHARED_AI\s*/\s*"([^"]+)"\s*/\s*"([^"]+\.md)"'
    )
    for match in path_pattern_2.finditer(content):
        parts = match.groups()
        target = SHARED_AI / parts[0] / parts[1]
        target_str = str(target)

        if target_str in targets_checked:
            continue
        targets_checked.add(target_str)

        if target.exists():
            if verbose:
                result.ok(f"{'/'.join(parts)}: 存在")
        else:
            result.fail(f"{'/'.join(parts)}: 存在しない")

    if not targets_checked:
        result.warn("ターゲットパスを抽出できなかった（パターン不一致）")

    for line in result.details:
        print(line)
    print(f"  → {result.summary()}")
    return result


# ─── メイン ──────────────────────────────────────────────────────

ALL_CHECKS = {
    "links": check_links,
    "steering": check_steering,
    "agents": check_agents,
    "scripts": check_scripts,
    "interfaces": check_interfaces,
    "symlinks": check_symlinks,
    "resolve": check_resolve,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="README/ドキュメントの整合性を自動チェックする",
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
    print("  audit-documentation: README/ドキュメント整合性チェック")
    print("=" * 60)

    if args.check:
        checks = {args.check: ALL_CHECKS[args.check]}
    else:
        checks = ALL_CHECKS

    results: list[AuditResult] = []
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
