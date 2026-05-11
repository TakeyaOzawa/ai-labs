#!/usr/bin/env python3.12
"""
fetch-rss-feeds: 指定カテゴリのRSS/Atomフィードから新着記事を取得しMarkdownに出力する

目的:
    tech/biz/academic等のカテゴリ別に定義されたRSS/Atomフィードを巡回し、
    対象日の新着記事を収集してMarkdownファイルとして書き出す。
    日次・週次の情報収集パイプラインの入力データ生成に使用する。

使い方:
    python3.12 scripts/fetch-rss-feeds.py --category <tech|biz_car|academic|tech_events|lifestyle_events> --date <YYYY-MM-DD> [--output <path>] [--no-filter]

例:
    python3.12 scripts/fetch-rss-feeds.py --category tech --date 2026-05-05
    python3.12 scripts/fetch-rss-feeds.py --category biz_car --date 2026-05-05 --output /tmp/biz_car.md

出力: Markdown ファイル（対象日の新着記事一覧）
"""

import argparse
import sys
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

# ─── フィード定義 ───────────────────────────────────────────────

FEEDS = {
    "tech_events": [
        {
            "name": "connpass 新着イベント (IT)",
            "url": "https://connpass.com/explore/ja.atom",
            "type": "atom",
        },
        {
            "name": "TECH PLAY イベント",
            "url": "https://techplay.jp/event/rss",
            "type": "rss",
        },
        {
            "name": "Doorkeeper 新着",
            "url": "https://www.doorkeeper.jp/events.atom",
            "type": "atom",
        },
    ],
    "lifestyle_events": [
        {
            "name": "Walker plus イベント",
            "url": "https://www.walkerplus.com/rss/event/ar0313.xml",
            "type": "rss",
        },
        {
            "name": "レッツエンジョイ東京",
            "url": "https://www.enjoytokyo.jp/rss/event.xml",
            "type": "rss",
        },
        {
            "name": "Peatix 東京イベント",
            "url": "https://peatix.com/search/events.atom?country=JP&place=Tokyo",
            "type": "atom",
        },
    ],
    "tech": [
        {
            "name": "Qiita トレンド",
            "url": "https://qiita.com/popular-items/feed",
            "type": "atom",
        },
        {
            "name": "Zenn トレンド",
            "url": "https://zenn.dev/feed",
            "type": "rss",
        },
        {
            "name": "Hacker News (50+ points)",
            "url": "https://hnrss.org/newest?points=50",
            "type": "rss",
        },
        {
            "name": "Laravel News",
            "url": "https://laravel-news.com/feed",
            "type": "rss",
        },
        {
            "name": "AWS Blog",
            "url": "https://aws.amazon.com/blogs/aws/feed/",
            "type": "rss",
        },
        {
            "name": "GitHub Blog",
            "url": "https://github.blog/feed/",
            "type": "rss",
        },
        {
            "name": "Node.js Blog",
            "url": "https://nodejs.org/en/feed/blog.xml",
            "type": "rss",
        },
        {
            "name": "TypeScript Blog",
            "url": "https://devblogs.microsoft.com/typescript/feed/",
            "type": "rss",
        },
        {
            "name": ".NET Blog",
            "url": "https://devblogs.microsoft.com/dotnet/feed/",
            "type": "rss",
        },
        {
            "name": "Publickey",
            "url": "https://www.publickey1.jp/atom.xml",
            "type": "atom",
        },
        {
            "name": "The Hacker News (Security)",
            "url": "https://feeds.feedburner.com/TheHackersNews",
            "type": "rss",
        },
        {
            "name": "Lobsters",
            "url": "https://lobste.rs/rss",
            "type": "rss",
        },
        {
            "name": "DEV Community",
            "url": "https://dev.to/feed",
            "type": "rss",
        },
        {
            "name": "Vercel Blog",
            "url": "https://vercel.com/atom",
            "type": "atom",
        },
        {
            "name": "Google Developers Blog",
            "url": "https://developers.googleblog.com/feeds/posts/default",
            "type": "atom",
        },
        {
            "name": "SecurityWeek",
            "url": "https://www.securityweek.com/feed/",
            "type": "rss",
        },
        {
            "name": "Gihyo.jp",
            "url": "https://gihyo.jp/feed/rss2",
            "type": "rss",
        },
        {
            "name": "Ars Technica",
            "url": "https://arstechnica.com/feed",
            "type": "rss",
        },
        {
            "name": "The Register",
            "url": "https://www.theregister.com/feed",
            "type": "rss",
        },
        {
            "name": "Simon Willison's Weblog",
            "url": "https://simonwillison.net/atom/everything/",
            "type": "atom",
        },
        {
            "name": "OpenAI Blog",
            "url": "https://openai.com/blog/rss.xml",
            "type": "rss",
        },
        {
            "name": "Docker Blog",
            "url": "https://www.docker.com/feed",
            "type": "rss",
        },
        {
            "name": "Kubernetes Blog",
            "url": "https://kubernetes.io/feed.xml",
            "type": "rss",
        },
        {
            "name": "Hackaday",
            "url": "https://hackaday.com/feed",
            "type": "rss",
        },
        {
            "name": "InfoQ",
            "url": "https://www.infoq.com/feed",
            "type": "rss",
        },
        {
            "name": "Krebs on Security",
            "url": "https://krebsonsecurity.com/feed",
            "type": "rss",
        },
        {
            "name": "It's FOSS",
            "url": "https://itsfoss.com/feed",
            "type": "atom",
        },
        {
            "name": "The Next Web",
            "url": "https://thenextweb.com/feed",
            "type": "rss",
        },
        {
            "name": "Zed Blog",
            "url": "https://zed.dev/blog.rss",
            "type": "rss",
        },
        {
            "name": "Help Net Security",
            "url": "https://www.helpnetsecurity.com/feed",
            "type": "rss",
        },
    ],
    "biz_car": [
        {
            "name": "Response (自動車総合)",
            "url": "https://response.jp/rss/index.rdf",
            "type": "rss",
        },
        {
            "name": "Car Watch",
            "url": "https://car.watch.impress.co.jp/data/rss/1.0/car/feed.rdf",
            "type": "rss",
        },
        {
            "name": "くるまのニュース",
            "url": "https://kuruma-news.jp/feed",
            "type": "rss",
        },
        {
            "name": "TechCrunch",
            "url": "https://techcrunch.com/feed/",
            "type": "rss",
        },
        {
            "name": "BRIDGE (スタートアップ)",
            "url": "https://thebridge.jp/feed",
            "type": "rss",
        },
        {
            "name": "ITmedia ビジネス",
            "url": "https://rss.itmedia.co.jp/rss/2.0/business.xml",
            "type": "rss",
        },
        {
            "name": "東洋経済オンライン",
            "url": "https://toyokeizai.net/list/feed/rss",
            "type": "rss",
        },
        {
            "name": "Electrek",
            "url": "https://electrek.co/feed",
            "type": "rss",
        },
        {
            "name": "Automotive World",
            "url": "https://www.automotiveworld.com/feed",
            "type": "rss",
        },
        {
            "name": "TeslaNorth",
            "url": "https://teslanorth.com/feed",
            "type": "rss",
        },
    ],
    "academic": [
        {
            "name": "arXiv cs.AI",
            "url": "https://rss.arxiv.org/rss/cs.AI",
            "type": "rss",
        },
        {
            "name": "arXiv cs.LG (Machine Learning)",
            "url": "https://rss.arxiv.org/rss/cs.LG",
            "type": "rss",
        },
        {
            "name": "arXiv cs.CV (Computer Vision)",
            "url": "https://rss.arxiv.org/rss/cs.CV",
            "type": "rss",
        },
        {
            "name": "arXiv cs.SE (Software Engineering)",
            "url": "https://rss.arxiv.org/rss/cs.SE",
            "type": "rss",
        },
        {
            "name": "arXiv cs.RO (Robotics/Drones)",
            "url": "https://rss.arxiv.org/rss/cs.RO",
            "type": "rss",
        },
        {
            "name": "arXiv econ.GN (General Economics)",
            "url": "https://rss.arxiv.org/rss/econ.GN",
            "type": "rss",
        },
        {
            "name": "Hugging Face Papers",
            "url": "https://huggingface.co/blog/feed.xml",
            "type": "rss",
        },
        {
            "name": "NBER New Working Papers",
            "url": "https://www.nber.org/rss/new.xml",
            "type": "rss",
        },
        {
            "name": "J-STAGE 新着",
            "url": "https://www.jstage.jst.go.jp/AF12S010Init/-char/ja/rss/general",
            "type": "rss",
        },
        {
            "name": "Papers With Code (trending)",
            "url": "https://paperswithcode.com/latest",
            "type": "html_fallback",
        },
    ],
}

# ─── フィード取得・パース ────────────────────────────────────────

def fetch_feed(url: str, timeout: int = 15) -> str | None:
    """URLからフィードXMLを取得する。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RSS Feed Reader)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️  取得失敗: {url} ({e})", file=sys.stderr)
        return None


def parse_rss(xml_text: str, max_items: int = 500) -> list[dict]:
    """RSS 2.0 / RDF をパースして記事リストを返す。"""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date = item.findtext("pubDate", "")
        description = item.findtext("description", "")[:200].strip()
        if title and link:
            items.append({
                "title": title,
                "url": link,
                "date": pub_date,
                "summary": description,
            })
        if len(items) >= max_items:
            break
    return items


def parse_atom(xml_text: str, max_items: int = 500) -> list[dict]:
    """Atomフィードをパースして記事リストを返す。"""
    items = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip()
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""
        updated = entry.findtext("atom:updated", "", ns)
        summary = entry.findtext("atom:summary", "", ns)[:200].strip()
        if title and link:
            items.append({
                "title": title,
                "url": link,
                "date": updated,
                "summary": summary,
            })
        if len(items) >= max_items:
            break
    return items


def filter_by_date(items: list[dict], target_date: str) -> list[dict]:
    """対象日（とその前日）の記事のみフィルタする。日付パース失敗時は全件通す。"""
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return items

    filtered = []
    for item in items:
        date_str = item.get("date", "")
        if not date_str:
            filtered.append(item)  # 日付なしは通す
            continue
        try:
            # RFC 2822 (RSS)
            dt = parsedate_to_datetime(date_str).date()
        except (ValueError, TypeError):
            try:
                # ISO 8601 (Atom)
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                filtered.append(item)  # パース失敗は通す
                continue
        # 対象日 or 前日の記事を含める
        if target - timedelta(days=1) <= dt <= target:
            filtered.append(item)

    return filtered


# ─── 出力 ────────────────────────────────────────────────────────

def format_markdown(feed_name: str, items: list[dict]) -> str:
    """記事リストをMarkdown形式に変換する。"""
    if not items:
        return f"## {feed_name}\n\n_新着記事なし_\n\n"

    lines = [f"## {feed_name}\n"]
    for item in items:
        title = item["title"].replace("[", "\\[").replace("]", "\\]")
        lines.append(f"- [{title}]({item['url']})")
        if item.get("summary"):
            # HTMLタグ除去（簡易）
            summary = item["summary"].replace("<", " ").replace(">", " ")[:150]
            lines.append(f"  - {summary}")
    lines.append("")
    return "\n".join(lines)


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="RSS/Atomフィード取得")
    parser.add_argument("--category", required=True, choices=["tech", "biz_car", "academic", "tech_events", "lifestyle_events"],
                        help="取得カテゴリ")
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--output", help="出力ファイルパス（省略時は自動決定）")
    parser.add_argument("--no-filter", action="store_true",
                        help="日付フィルタを無効化（全件出力）")
    args = parser.parse_args()

    # 出力先決定
    output_dirs = {
        "tech": "Documents/works/scout_histories/tech_trends/daily",
        "biz_car": "Documents/works/scout_histories/biz_car_trends/daily",
        "academic": "Documents/works/scout_histories/academic_trends/daily",
        "tech_events": "Documents/works/scout_histories/tech_events/weekly",
        "lifestyle_events": "Documents/works/scout_histories/lifestyle_events/daily",
    }
    if args.output:
        output_path = Path(args.output)
    else:
        home = Path.home()
        output_path = home / output_dirs[args.category] / f".tmp_{args.date}_feeds.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    feeds = FEEDS.get(args.category, [])
    if not feeds:
        print(f"❌ カテゴリ '{args.category}' のフィード定義がありません", file=sys.stderr)
        sys.exit(1)

    print(f"📡 {args.category} フィード取得開始（対象日: {args.date}、{len(feeds)}フィード）")

    results = []
    success_count = 0
    fail_count = 0

    for feed in feeds:
        print(f"  → {feed['name']}...", end=" ")

        if feed["type"] == "html_fallback":
            print("⏭️  スキップ（HTML/JSサイト）")
            continue

        xml_text = fetch_feed(feed["url"])
        if xml_text is None:
            fail_count += 1
            continue

        if feed["type"] == "atom":
            items = parse_atom(xml_text)
        else:
            items = parse_rss(xml_text)

        if not args.no_filter:
            items = filter_by_date(items, args.date)

        results.append(format_markdown(feed["name"], items))
        success_count += 1
        print(f"✅ {len(items)}件")

    # ファイル書き出し
    header = f"# {args.category.upper()} フィード新着: {args.date}\n\n"
    header += f"取得: {success_count}成功 / {fail_count}失敗 / {len(feeds)}フィード\n\n---\n\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(results))

    print(f"\n✅ 完了: {output_path}")
    print(f"   {success_count}/{len(feeds)} フィード取得成功")



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
