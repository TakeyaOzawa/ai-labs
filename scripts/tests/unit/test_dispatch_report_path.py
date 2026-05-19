"""
test_dispatch_report_path: dispatch-agent-wrapper のレポートパス検出ロジックのテスト

対象: dispatch-agent-wrapper.py の extract_report_path / _find_path_in_text / _resolve_path

テスト観点:
    - キーワード付きパターン（出力/保存先/レポート/ファイル）
    - ANSIエスケープシーケンス付き出力
    - Creating: パターン（相対パス/絶対パス/~/形式）
    - バッククォート囲みパターン
    - 除外パス（/tmp/, /scout_reports/）
    - 優先順位（キーワード > フォールバック末尾優先）
    - JSON result フィールドからの抽出
"""

import json
import re
from pathlib import Path

import pytest

# ─── テスト対象のロジック（dispatch-agent-wrapper.py から抽出） ─────

_KEYWORD_PATTERNS = [
    re.compile(
        r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?"
        r"`?((?:~/)?Documents/works/[^\s`\"\x1b]+\.md)`?"
    ),
    re.compile(
        r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]{0,10}?"
        r"`?(\S+/works/[^\s`\"\x1b]+\.md)`?"
    ),
    re.compile(
        r"(?:出力|保存先|保存済み|レポート|ファイル|計画)[^\n]*?"
        r"(?:\x1b\[[0-9;]*m)*`?((?:~/)?Documents/works/[^\s`\"\x1b]+\.md)`?"
    ),
]
_FALLBACK_PATTERNS = [
    re.compile(
        r"(?:Creating|Updating|Appending to):\s*(?:\x1b\[[0-9;]*m)*"
        r"((?:~/|/[^\s`\"\x1b]*?)?Documents/works/[^\s`\"\x1b]+\.md)"
    ),
    re.compile(r"`((?:~/)?Documents/works/(?!scout_reports/)(?!tmp/)[^\s`\"\x1b]+\.md)`"),
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


# ═══════════════════════════════════════════════════════════════════
# テスト
# ═══════════════════════════════════════════════════════════════════


class TestKeywordPatterns:
    """キーワード付きパターンの正規表現マッチテスト。"""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text,expected",
        [
            (
                '> 保存先: `Documents/works/research_materials/2026-05-16_ollama.md`',
                "Documents/works/research_materials/2026-05-16_ollama.md",
            ),
            (
                '> レポート保存先: `Documents/works/research_materials/2026-05-16_ollama.md`',
                "Documents/works/research_materials/2026-05-16_ollama.md",
            ),
            (
                "調査レポートは ~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md に保存されました。",
                "~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
            ),
            (
                "出力ファイル: ~/Documents/works/research_materials/2026-05-17_test.md",
                "~/Documents/works/research_materials/2026-05-17_test.md",
            ),
            (
                "検証計画は~/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.mdに保存済みです。",
                "~/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
            ),
        ],
    )
    def test_keyword_pattern_0_matches(self, text, expected):
        match = _KEYWORD_PATTERNS[0].search(text)
        assert match is not None
        assert match.group(1) == expected

    @pytest.mark.unit
    def test_ansi_escape_removed_before_match(self):
        ansi_text = (
            "調査レポートは \x1b[38;5;10m~/Documents/works/research_materials/"
            "2026-05-17_open-clew-engineer-guide.md\x1b[0m に保存されました。"
        )
        ansi_clean = re.sub(r"\x1b\[[0-9;]*m", "", ansi_text)
        match = _KEYWORD_PATTERNS[0].search(ansi_clean)
        assert match is not None
        assert (
            match.group(1)
            == "~/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md"
        )


class TestCreatingPattern:
    """Creating: パターンのテスト。"""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text,expected",
        [
            (
                "Creating: Documents/works/tech_poc_plans/2026-05-17_openclaw-personal-ai-assistant.md",
                "Documents/works/tech_poc_plans/2026-05-17_openclaw-personal-ai-assistant.md",
            ),
            (
                "Creating: /Users/takeya_ozawa/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
                "/Users/takeya_ozawa/Documents/works/research_materials/2026-05-17_open-clew-engineer-guide.md",
            ),
            (
                "Creating: ~/Documents/works/research_materials/test.md",
                "~/Documents/works/research_materials/test.md",
            ),
            (
                "Creating: \x1b[38;5;141mDocuments/works/tech_poc_plans/test.md\x1b[0m",
                "Documents/works/tech_poc_plans/test.md",
            ),
            (
                "Creating: \x1b[38;5;141m/Users/takeya_ozawa/Documents/works/tech_poc_plans/test.md\x1b[0m",
                "/Users/takeya_ozawa/Documents/works/tech_poc_plans/test.md",
            ),
            (
                "Updating: Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
                "Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
            ),
            (
                "Updating: /Users/takeya_ozawa/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
                "/Users/takeya_ozawa/Documents/works/tech_poc_plans/2026-05-18_rfriends3-radio-recording-tool.md",
            ),
        ],
    )
    def test_creating_pattern_matches(self, text, expected):
        match = _FALLBACK_PATTERNS[0].search(text)
        assert match is not None
        assert match.group(1) == expected


class TestExcludedPaths:
    """除外パスのテスト。"""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        [
            "Creating: Documents/works/tmp/raw_results.md",
            "Creating: /Users/takeya_ozawa/Documents/works/research_materials/tmp/raw_results.md",
            "Creating: Documents/works/scout_reports/daily/2026-05-17_report.md",
        ],
    )
    def test_excluded_path_segments(self, text):
        match = _FALLBACK_PATTERNS[0].search(text)
        if match:
            path_str = match.group(1)
            assert any(seg in path_str for seg in _EXCLUDED_PATH_SEGMENTS)

    @pytest.mark.unit
    def test_backtick_scout_reports_excluded(self):
        match = _FALLBACK_PATTERNS[1].search(
            "`~/Documents/works/scout_reports/daily/2026-05-17.md`"
        )
        assert match is None

    @pytest.mark.unit
    def test_backtick_tmp_excluded(self):
        match = _FALLBACK_PATTERNS[1].search("`~/Documents/works/tmp/raw_results.md`")
        assert match is None


class TestPriority:
    """優先順位の統合テスト。"""

    @pytest.mark.unit
    def test_keyword_priority_over_creating(self, tmp_path):
        """キーワードがフォールバックより優先される。"""
        (tmp_path / "Documents" / "works" / "research_materials").mkdir(parents=True)
        (tmp_path / "Documents" / "works" / "tech_poc_plans").mkdir(parents=True)
        keyword_file = tmp_path / "Documents/works/research_materials/keyword-test.md"
        creating_file = tmp_path / "Documents/works/tech_poc_plans/creating-test.md"
        keyword_file.write_text("test")
        creating_file.write_text("test")

        log = (
            "Creating: Documents/works/tech_poc_plans/creating-test.md\n"
            "レポート: Documents/works/research_materials/keyword-test.md"
        )
        result = _find_path_in_text(log, tmp_path)
        assert result == keyword_file

    @pytest.mark.unit
    def test_fallback_last_valid_path(self, tmp_path):
        """フォールバック: 末尾優先（tmp除外）。"""
        (tmp_path / "Documents" / "works" / "research_materials" / "tmp").mkdir(parents=True)
        (tmp_path / "Documents" / "works" / "tech_poc_plans").mkdir(parents=True)
        tmp_file = tmp_path / "Documents/works/research_materials/tmp/raw_results.md"
        valid_file = tmp_path / "Documents/works/tech_poc_plans/creating-test.md"
        tmp_file.write_text("test")
        valid_file.write_text("test")

        log = (
            "Creating: Documents/works/research_materials/tmp/raw_results.md\n"
            "Creating: Documents/works/tech_poc_plans/creating-test.md"
        )
        result = _find_path_in_text(log, tmp_path)
        assert result == valid_file


class TestJsonResult:
    """JSON result フィールドからの抽出テスト。"""

    @pytest.mark.unit
    def test_extract_from_json_result(self, tmp_path):
        (tmp_path / "Documents" / "works" / "research_materials").mkdir(parents=True)
        target = tmp_path / "Documents/works/research_materials/keyword-test.md"
        target.write_text("test")

        json_log = (
            '{"type":"result","result":"完了しました。\\n\\n> 保存先: '
            '`Documents/works/research_materials/keyword-test.md`"}'
        )
        result = extract_report_path(json_log, tmp_path)
        assert result == target


class TestResolvePath:
    """_resolve_path のテスト。"""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "path_str,expected_fn",
        [
            (
                "~/Documents/works/research_materials/test.md",
                lambda home: home / "Documents/works/research_materials/test.md",
            ),
            (
                "Documents/works/tech_poc_plans/test.md",
                lambda home: home / "Documents/works/tech_poc_plans/test.md",
            ),
            (
                "/Users/takeya_ozawa/Documents/works/test.md",
                lambda _: Path("/Users/takeya_ozawa/Documents/works/test.md"),
            ),
            ("works/test.md", lambda _: None),
        ],
    )
    def test_resolve_path(self, path_str, expected_fn):
        home = Path.home()
        expected = expected_fn(home)
        result = _resolve_path(path_str, home)
        assert result == expected
