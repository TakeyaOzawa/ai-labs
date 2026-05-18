#!/usr/bin/env python3.12
"""
test_rss_source_updater: rss_source_updater.py のURL抽出・ドメイン分析ロジックのテスト

対象: scripts/rss_source_updater.py の extract_urls / get_domain / is_excluded_domain

使い方:
    python3.12 scripts/tests/test_rss_source_updater.py

テスト観点:
    - Markdown link形式からのURL抽出
    - bare URL形式からのURL抽出
    - ドメイン抽出と正規化
    - 除外ドメインのフィルタリング
    - 画像URLの除外
"""

import re
import sys
import urllib.parse
from pathlib import Path
from typing import Set

# ─── テスト対象のロジック（rss_source_updater.py から抽出） ─────

EXCLUDED_DOMAINS = {
    "notion.so", "github.com", "slack.com", "localhost",
    "127.0.0.1", "example.com", "volare.slack.com",
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


# ─── テストユーティリティ ────────────────────────────────────────

PASS = 0
FAIL = 0


def assert_eq(test_name: str, actual, expected) -> None:
    global PASS, FAIL
    if actual == expected:
        print(f"  ✅ {test_name}")
        PASS += 1
    else:
        print(f"  ❌ {test_name}")
        print(f"     expected: {expected}")
        print(f"     got:      {actual}")
        FAIL += 1


def assert_contains(test_name: str, collection: set, item: str) -> None:
    global PASS, FAIL
    if item in collection:
        print(f"  ✅ {test_name}")
        PASS += 1
    else:
        print(f"  ❌ {test_name}")
        print(f"     '{item}' not found in {sorted(collection)[:5]}...")
        FAIL += 1


def assert_not_contains(test_name: str, collection: set, item: str) -> None:
    global PASS, FAIL
    if item not in collection:
        print(f"  ✅ {test_name}")
        PASS += 1
    else:
        print(f"  ❌ {test_name}")
        print(f"     '{item}' should NOT be in collection but was found")
        FAIL += 1


# ─── テスト実行 ──────────────────────────────────────────────────

print("=" * 60)
print("rss_source_updater URL抽出・ドメイン分析テスト")
print("=" * 60)

# --- Section 1: Markdown link形式 ---
print("\n--- 1. Markdown link形式からのURL抽出 ---")

md_content = """
- [Anthropic Routines](https://www.infoq.com/news/2026/05/anthropic-routines/)
- [Deno Blog](https://deno.com/blog/v2.3)
- [AWS News](https://aws.amazon.com/about-aws/whats-new/2026/04/test/)
"""
domains = extract_domains_from_markdown(md_content)
assert_contains("infoq.com 抽出", domains, "www.infoq.com")
assert_contains("deno.com 抽出", domains, "deno.com")
assert_contains("aws.amazon.com 抽出", domains, "aws.amazon.com")

# --- Section 2: bare URL形式 ---
print("\n--- 2. bare URL形式からのURL抽出 ---")

bare_content = """
参考: https://techcommunity.microsoft.com/blog/exchange/test/123
詳細は https://socket.dev/blog/pnpm-11 を参照
"""
domains = extract_domains_from_markdown(bare_content)
assert_contains("techcommunity.microsoft.com 抽出", domains, "techcommunity.microsoft.com")
assert_contains("socket.dev 抽出", domains, "socket.dev")

# --- Section 3: 除外ドメイン ---
print("\n--- 3. 除外ドメインのフィルタリング ---")

excluded_content = """
- [PR #123](https://github.com/org/repo/pull/123)
- [Notion Page](https://notion.so/workspace/page-id)
- [Slack Thread](https://volare.slack.com/archives/C123/p456)
- [Valid Site](https://valid-site.example.org/article)
"""
domains = extract_domains_from_markdown(excluded_content)
assert_not_contains("github.com 除外", domains, "github.com")
assert_not_contains("notion.so 除外", domains, "notion.so")
assert_not_contains("volare.slack.com 除外", domains, "volare.slack.com")
assert_contains("valid-site.example.org 保持", domains, "valid-site.example.org")

# --- Section 4: 画像URL除外 ---
print("\n--- 4. 画像URLの除外 ---")

image_content = """
![logo](https://cdn.example.org/logo.png)
![icon](https://images.example.org/icon.svg)
- [Article](https://blog.example.org/article)
"""
domains = extract_domains_from_markdown(image_content)
assert_not_contains("png画像ドメイン除外", domains, "cdn.example.org")
assert_not_contains("svg画像ドメイン除外", domains, "images.example.org")
assert_contains("通常記事ドメイン保持", domains, "blog.example.org")

# --- Section 5: 混合コンテンツ ---
print("\n--- 5. 混合コンテンツ（実際のレポート形式） ---")

mixed_content = """
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
domains = extract_domains_from_markdown(mixed_content)
assert_contains("infoq.com", domains, "www.infoq.com")
assert_contains("the-decoder.com", domains, "the-decoder.com")
assert_contains("exploitbench.ai", domains, "exploitbench.ai")
assert_not_contains("github.com 除外", domains, "github.com")
assert_not_contains("画像ドメイン除外", domains, "diagrams.example.com")
assert_contains("aws.amazon.com", domains, "aws.amazon.com")

# --- Section 6: エッジケース ---
print("\n--- 6. エッジケース ---")

edge_content = ""
domains = extract_domains_from_markdown(edge_content)
assert_eq("空文字列 → 空セット", domains, set())

no_url_content = "これはURLを含まないテキストです。"
domains = extract_domains_from_markdown(no_url_content)
assert_eq("URL無し → 空セット", domains, set())

# ─── 結果サマリー ────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"結果: {PASS} passed, {FAIL} failed")
print("=" * 60)

sys.exit(1 if FAIL > 0 else 0)
