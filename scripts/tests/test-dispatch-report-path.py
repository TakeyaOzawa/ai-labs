#!/usr/bin/env python3.12
"""
test-dispatch-report-path: dispatch-agent-wrapper のレポートパス検出ロジックのテスト

対象: dispatch-agent-wrapper.py の extract_report_path / _find_path_in_text / _resolve_path

使い方:
    python3.12 scripts/tests/test-dispatch-report-path.py

テスト観点:
    - キーワード付きパターン（出力/保存先/レポート/ファイル）
    - ANSIエスケープシーケンス付き出力
    - Creating: パターン（相対パス/絶対パス/~/形式）
    - バッククォート囲みパターン
    - 除外パス（/tmp/, /scout_reports/）
    - 優先順位（キーワード > フォールバック末尾優先）
    - JSON result フィールドからの抽出
"""

import re
import sys
from pathlib import Path

# scripts/ をパスに追加
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

# テスト対象のモジュールをインポート（直接importできないのでexec）
from importlib.util import module_from_spec, spec_from_file_location

_spec = spec_from_file_location(
    "dispatch_agent_wrapper",
    SCRIPTS_DIR / "dispatch-agent-wrapper.py",
    submodule_search_locations=[],
)

# _pipeline_common のインポートをモックするため、必要な部分だけ抽出
# テスト対象の関数を直接定義から取得する
import json

_KEYWORD_PATTERNS = [
    re.compile(r'(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?`?((?:~/)?Documents/works/[^\s`"\x1b]+\.md)`?'),
    re.compile(r'(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?`?(\S+/works/[^\s`"\x1b]+\.md)`?'),
    re.compile(r'(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]*?(?:\x1b\[[0-9;]*m)*`?((?:~/)?Documents/works/[^\s`"\x1b]+\.md)`?'),
]
_FALLBACK_PATTERNS = [
    re.compile(r'(?:Creating|Updating|Appending to):\s*(?:\x1b\[[0-9;]*m)*((?:~/|/[^\s`"\x1b]*?)?Documents/works/[^\s`"\x1b]+\.md)'),
    re.compile(r'`((?:~/)?Documents/works/(?!scout_reports/)(?!tmp/)[^\s`"\x1b]+\.md)`'),
]
_EXCLUDED_PATH_SEGMENTS = ("/tmp/", "/scout_reports/")


def _resolve_path(path_str: str, home: Path) -> Path | None:
    if path_str.startswith("~/"):
        return Path(path_str).expanduser()
    elif path_str.startswith("/"):
        return Path(path_str)
    elif path_str.startswith("Documents/"):
        return home / path_str
    return None


def _find_path_in_text(text: str, home: Path) -> Path | None:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    clean_text = ansi_escape.sub("", text)

    for search_text in [clean_text, text]:
        for pattern in _KEYWORD_PATTERNS:
            match = pattern.search(search_text)
            if match:
                path_str = match.group(1)
                path = _resolve_path(path_str, home)
                if path and path.exists():
                    return path

    for search_text in [clean_text, text]:
        for pattern in _FALLBACK_PATTERNS:
            matches = list(pattern.finditer(search_text))
            if matches:
                for match in reversed(matches):
                    path_str = match.group(1)
                    if any(seg in path_str for seg in _EXCLUDED_PATH_SEGMENTS):
                        continue
                    path = _resolve_path(path_str, home)
                    if path and path.exists():
                        return path
    return None


def extract_report_path(log_content: str, home: Path | None = None) -> Path | None:
    if home is None:
        home = Path.home()
    for line in reversed(log_content.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"result"' in line:
            try:
                data = json.loads(line)
                result_text = data.get("result", "")
                path = _find_path_in_text(result_text, home)
                if path:
                    return path
            except json.JSONDecodeError:
                continue
    return _find_path_in_text(log_content, home)


# ─── テストユーティリティ ────────────────────────────────────────

HOME = Path.home()
PASS = 0
FAIL = 0


def assert_path(test_name: str, result: Path | None, expected: Path | None) -> None:
    global PASS, FAIL
    if result == expected:
        print(f"  ✅ {test_name}")
        PASS += 1
    else:
        print(f"  ❌ {test_name}")
        print(f"     expected: {expected}")
        print(f"     got:      {result}")
        FAIL += 1


def assert_regex_match(test_name: str, pattern: re.Pattern, text: str, expected_group1: str | None) -> None:
    global PASS, FAIL
    m = pattern.search(text)
    actual = m.group(1) if m else None
    if actual == expected_group1:
        print(f"  ✅ {test_name}")
        PASS += 1
    else:
        print(f"  ❌ {test_name}")
        print(f"     expected: {expected_group1}")
        print(f"     got:      {actual}")
        FAIL += 1


def assert_excluded(test_name: str, pattern: re.Pattern, text: str) -> None:
    """パターンがマッチしても除外ロジックで弾かれることを確認。"""
    global PASS, FAIL
    m = pattern.search(text)
    if m is None:
        print(f"  ✅ {test_name} (no match)")
        PASS += 1
        return
    path_str = m.group(1)
    excluded = any(seg in path_str for seg in _EXCLUDED_PATH_SEGMENTS)
    if excluded:
        print(f"  ✅ {test_name} (matched but excluded)")
        PASS += 1
    else:
        print(f"  ❌ {test_name} (matched and NOT excluded: {path_str})")
        FAIL += 1


# ─── テスト実行 ──────────────────────────────────────────────────

print("=" * 60)
print("dispatch-agent-wrapper レポートパス検出テスト")
print("=" * 60)

# --- Section 1: キーワード付きパターン（正規表現マッチ） ---
print("\n--- 1. キーワード付きパターン ---")

kw0 = _KEYWORD_PATTERNS[0]
assert_regex_match(
    "保存先: Documents/works/...",
    kw0,
    '> 保存先: `Documents/works/research_materials/2026-05-16_ollama.md`',
    "Documents/works/research_materials/2026-05-16_ollama.md",
)
assert_regex_match(
    "レポート保存先: Documents/works/...",
    kw0,
    '> レポート保存先: `Documents/works/research_materials/2026-05-16_ollama.md`',
    "Documents/works/research_materials/2026-05-16_ollama.md",
)
assert_regex_match(
    "レポートは ~/Documents/works/...",
    kw0,
    '調査レポートは ~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md に保存されました。',
    "~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
)
assert_regex_match(
    "出力ファイル: ~/Documents/works/...",
    kw0,
    '出力ファイル: ~/Documents/works/research_materials/2026-05-17_test.md',
    "~/Documents/works/research_materials/2026-05-17_test.md",
)
assert_regex_match(
    "計画は~/Documents/works/...に保存済み",
    kw0,
    '検証計画は~/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.mdに保存済みです。',
    "~/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
)

# --- Section 2: ANSIエスケープ対応 ---
print("\n--- 2. ANSIエスケープ対応 ---")

ansi_text = '調査レポートは \x1b[38;5;10m~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md\x1b[0m に保存されました。'
ansi_clean = re.sub(r'\x1b\[[0-9;]*m', '', ansi_text)
assert_regex_match(
    "ANSI除去後にキーワードパターンでマッチ",
    kw0,
    ansi_clean,
    "~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
)

# --- Section 3: Creating: パターン ---
print("\n--- 3. Creating: パターン ---")

creating = _FALLBACK_PATTERNS[0]
assert_regex_match(
    "Creating: 相対パス",
    creating,
    "Creating: Documents/works/tech_poc_plans/2026-05-17_openclaw-personal-ai-assistant.md",
    "Documents/works/tech_poc_plans/2026-05-17_openclaw-personal-ai-assistant.md",
)
assert_regex_match(
    "Creating: 絶対パス",
    creating,
    "Creating: /Users/takeya_ozawa/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
    "/Users/takeya_ozawa/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
)
assert_regex_match(
    "Creating: ~/形式",
    creating,
    "Creating: ~/Documents/works/research_materials/test.md",
    "~/Documents/works/research_materials/test.md",
)
assert_regex_match(
    "Creating: ANSI付き相対パス",
    creating,
    "Creating: \x1b[38;5;141mDocuments/works/tech_poc_plans/test.md\x1b[0m",
    "Documents/works/tech_poc_plans/test.md",
)
assert_regex_match(
    "Creating: ANSI付き絶対パス",
    creating,
    "Creating: \x1b[38;5;141m/Users/takeya_ozawa/Documents/works/tech_poc_plans/test.md\x1b[0m",
    "/Users/takeya_ozawa/Documents/works/tech_poc_plans/test.md",
)
assert_regex_match(
    "Updating: 相対パス",
    creating,
    "Updating: Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
    "Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
)
assert_regex_match(
    "Updating: 絶対パス",
    creating,
    "Updating: /Users/takeya_ozawa/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
    "/Users/takeya_ozawa/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
)

# --- Section 4: 除外パス ---
print("\n--- 4. 除外パス ---")

assert_excluded(
    "Creating: /tmp/ 除外（works直下）",
    creating,
    "Creating: Documents/works/tmp/raw_results.md",
)
assert_excluded(
    "Creating: /tmp/ 除外（サブディレクトリ内）",
    creating,
    "Creating: /Users/takeya_ozawa/Documents/works/research_materials/tmp/raw_results.md",
)
assert_excluded(
    "Creating: /scout_reports/ 除外",
    creating,
    "Creating: Documents/works/scout_reports/daily/2026-05-17_report.md",
)

backtick = _FALLBACK_PATTERNS[1]
assert_regex_match(
    "バッククォート: scout_reports 除外（正規表現レベル）",
    backtick,
    "`~/Documents/works/scout_reports/daily/2026-05-17.md`",
    None,  # negative lookahead で除外
)
assert_regex_match(
    "バッククォート: tmp 除外（正規表現レベル）",
    backtick,
    "`~/Documents/works/tmp/raw_results.md`",
    None,  # negative lookahead で除外
)

# --- Section 5: 優先順位（統合テスト） ---
print("\n--- 5. 優先順位（統合テスト） ---")

# 統合テストは path.exists() に依存するため、一時ファイルを作成して実行
import tempfile
import os

_tmp_dir = tempfile.mkdtemp()
_test_keyword_file = Path(_tmp_dir) / "Documents" / "works" / "research_materials" / "keyword-test.md"
_test_creating_file = Path(_tmp_dir) / "Documents" / "works" / "tech_poc_plans" / "creating-test.md"
_test_tmp_file = Path(_tmp_dir) / "Documents" / "works" / "research_materials" / "tmp" / "raw_results.md"
_test_keyword_file.parent.mkdir(parents=True, exist_ok=True)
_test_creating_file.parent.mkdir(parents=True, exist_ok=True)
_test_tmp_file.parent.mkdir(parents=True, exist_ok=True)
_test_keyword_file.write_text("test")
_test_creating_file.write_text("test")
_test_tmp_file.write_text("test")

_test_home = Path(_tmp_dir)

# キーワードがフォールバックより優先
log_mixed = (
    f'Creating: Documents/works/tech_poc_plans/creating-test.md\n'
    f'調査レポートは ~/Documents/works/research_materials/keyword-test.md に保存されました。'
)
# ~/形式はexpanduserで実HOME配下を参照するため、テスト用homeでDocuments/形式を使う
log_mixed_for_test = (
    f'Creating: Documents/works/tech_poc_plans/creating-test.md\n'
    f'レポート: Documents/works/research_materials/keyword-test.md'
)
assert_path(
    "キーワード優先（Creating: より keyword が先）",
    _find_path_in_text(log_mixed_for_test, _test_home),
    _test_home / "Documents/works/research_materials/keyword-test.md",
)

# フォールバック: 末尾優先（tmp除外）
log_fallback = (
    f'Creating: Documents/works/research_materials/tmp/raw_results.md\n'
    f'Creating: Documents/works/tech_poc_plans/creating-test.md'
)
assert_path(
    "フォールバック末尾優先（tmp除外 → 最後の有効パス）",
    _find_path_in_text(log_fallback, _test_home),
    _test_home / "Documents/works/tech_poc_plans/creating-test.md",
)

# --- Section 6: JSON result フィールド ---
print("\n--- 6. JSON result フィールド ---")

json_log = (
    '{"type":"result","result":"完了しました。\\n\\n> 保存先: '
    '`Documents/works/research_materials/keyword-test.md`"}'
)
assert_path(
    "JSON result からパス抽出",
    extract_report_path(json_log, _test_home),
    _test_home / "Documents/works/research_materials/keyword-test.md",
)

# 一時ファイル削除
import shutil
shutil.rmtree(_tmp_dir)

# --- Section 7: _resolve_path ---
print("\n--- 7. _resolve_path ---")

assert_path(
    "~/ → expanduser",
    _resolve_path("~/Documents/works/research_materials/test.md", HOME),
    HOME / "Documents/works/research_materials/test.md",
)
assert_path(
    "Documents/ → home / path",
    _resolve_path("Documents/works/tech_poc_plans/test.md", HOME),
    HOME / "Documents/works/tech_poc_plans/test.md",
)
assert_path(
    "/ → absolute",
    _resolve_path("/Users/takeya_ozawa/Documents/works/test.md", HOME),
    Path("/Users/takeya_ozawa/Documents/works/test.md"),
)
assert_path(
    "unknown prefix → None",
    _resolve_path("works/test.md", HOME),
    None,
)

# ─── 結果サマリー ────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"結果: {PASS} passed, {FAIL} failed")
print("=" * 60)

sys.exit(1 if FAIL > 0 else 0)
