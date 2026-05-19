"""
test_rss_source_updater: rss-source-updater.py のURL抽出・ドメイン分析ロジックのテスト

対象: scripts/rss-source-updater.py の extract_domains_from_markdown

テスト観点:
    - Markdown link形式からのURL抽出
    - bare URL形式からのURL抽出
    - ドメイン抽出と正規化
    - 除外ドメインのフィルタリング
    - 画像URLの除外
"""

import re
import urllib.parse
from typing import Set

import pytest

# ─── テスト対象のロジック（rss-source-updater.py から抽出） ─────

EXCLUDED_DOMAINS = {
    "notion.so",
    "github.com",
    "slack.com",
    "localhost",
    "127.0.0.1",
    "example.com",
    "volare.slack.com",
}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")


def extract_domains_from_markdown(content: str) -> Set[str]:
    """Markdownコンテンツからドメインを抽出する。"""
    urls: Set[str] = set()

    # Markdown link形式: [text](url)
    md_links = re.findall(r"\[.*?\]\((https?://[^\)]+)\)", content)
    urls.update(md_links)

    # bare URL形式: https://...
    bare_urls = re.findall(r"https?://[^\s\)\]\"']+", content)
    urls.update(bare_urls)

    # ドメイン抽出と除外処理
    domains: Set[str] = set()
    for url in urls:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if not domain:
                continue
            if any(exc in domain for exc in EXCLUDED_DOMAINS):
                continue
            if url.lower().endswith(IMAGE_EXTENSIONS):
                continue
            domains.add(domain)
        except Exception:
            continue

    return domains


# ═══════════════════════════════════════════════════════════════════
# テスト
# ═══════════════════════════════════════════════════════════════════


class TestMarkdownLinkExtraction:
    """Markdown link形式からのURL抽出テスト。"""

    @pytest.mark.unit
    def test_extracts_markdown_link_domains(self):
        content = """
- [Anthropic Routines](https://www.infoq.com/news/2026/05/anthropic-routines/)
- [Deno Blog](https://deno.com/blog/v2.3)
- [AWS News](https://aws.amazon.com/about-aws/whats-new/2026/04/test/)
"""
        domains = extract_domains_from_markdown(content)
        assert "www.infoq.com" in domains
        assert "deno.com" in domains
        assert "aws.amazon.com" in domains


class TestBareUrlExtraction:
    """bare URL形式からのURL抽出テスト。"""

    @pytest.mark.unit
    def test_extracts_bare_url_domains(self):
        content = """
参考: https://techcommunity.microsoft.com/blog/exchange/test/123
詳細は https://socket.dev/blog/pnpm-11 を参照
"""
        domains = extract_domains_from_markdown(content)
        assert "techcommunity.microsoft.com" in domains
        assert "socket.dev" in domains


class TestExcludedDomains:
    """除外ドメインのフィルタリングテスト。"""

    @pytest.mark.unit
    def test_excludes_known_domains(self):
        content = """
- [PR #123](https://github.com/org/repo/pull/123)
- [Notion Page](https://notion.so/workspace/page-id)
- [Slack Thread](https://volare.slack.com/archives/C123/p456)
- [Valid Site](https://valid-site.example.org/article)
"""
        domains = extract_domains_from_markdown(content)
        assert "github.com" not in domains
        assert "notion.so" not in domains
        assert "volare.slack.com" not in domains
        assert "valid-site.example.org" in domains


class TestImageUrlExclusion:
    """画像URLの除外テスト。"""

    @pytest.mark.unit
    def test_excludes_image_urls(self):
        content = """
![logo](https://cdn.example.org/logo.png)
![icon](https://images.example.org/icon.svg)
- [Article](https://blog.example.org/article)
"""
        domains = extract_domains_from_markdown(content)
        assert "cdn.example.org" not in domains
        assert "images.example.org" not in domains
        assert "blog.example.org" in domains


class TestMixedContent:
    """混合コンテンツ（実際のレポート形式）テスト。"""

    @pytest.mark.unit
    def test_mixed_content_extraction(self):
        content = """
## 技術トレンド 2026-05-17

### 1. AI/ML
- [Claude Code Routines](https://www.infoq.com/news/2026/05/anthropic-routines-claude/)
  - 参考: https://the-decoder.com/new-benchmark/

### 2. セキュリティ
- [ExploitBench](https://exploitbench.ai/) - 新しいベンチマーク
  - GitHub: https://github.com/exploitbench/exploitbench (除外対象)

### 3. インフラ
- ![diagram](https://diagrams.example.com/arch.png)
- [AWS Interconnect](https://aws.amazon.com/about-aws/whats-new/2026/04/interconnect/)
"""
        domains = extract_domains_from_markdown(content)
        assert "www.infoq.com" in domains
        assert "the-decoder.com" in domains
        assert "exploitbench.ai" in domains
        assert "github.com" not in domains
        assert "diagrams.example.com" not in domains
        assert "aws.amazon.com" in domains


class TestEdgeCases:
    """エッジケーステスト。"""

    @pytest.mark.unit
    def test_empty_string_returns_empty_set(self):
        assert extract_domains_from_markdown("") == set()

    @pytest.mark.unit
    def test_no_urls_returns_empty_set(self):
        assert extract_domains_from_markdown("これはURLを含まないテキストです。") == set()
