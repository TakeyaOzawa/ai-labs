#!/usr/bin/env python3.12
"""
rss-source-updater: レポートから未登録サイトを発見しRSS有無を調査してソース定義を自動更新

目的:
    trend/digestレポートに含まれるURLから未登録サイトを検出し、
    RSS/Atomフィードの有無を探索して、fetch-rss-feeds.py・references・
    プロンプトファイルを自動更新する。
    日次パイプラインの後処理として実行し、情報収集カバレッジを自動拡張する。

使い方:
    python3.12 scripts/rss/rss-source-updater.py --date <YYYY-MM-DD> [オプション]

例:
    python3.12 scripts/rss/rss-source-updater.py --date 2026-05-18
    python3.12 scripts/rss/rss-source-updater.py --date 2026-05-18 --dry-run
    python3.12 scripts/rss/rss-source-updater.py --date 2026-05-18 --categories tech biz_car
    python3.12 scripts/rss/rss-source-updater.py --files ~/Documents/works/scout_reports/tech_trends/daily/2026-05-18_tech_trends.md
    python3.12 scripts/rss/rss-source-updater.py --domains techcrunch.com modal.com --category tech
    python3.12 scripts/rss/rss-source-updater.py --date 2026-05-18 --max-sites 5 --timeout 5

出力: JSON（標準出力）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import argparse
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Set

from logger import get_logger

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

CATEGORY_CONFIG: dict[str, dict[str, str]] = {
    "tech": {
        "report_dir": "tech_trends",
        "feeds_category": "tech",
        "references_file": "tech-trend-sources.md",
        "prompt_file": "tech-trend-scout.md",
    },
    "biz_car": {
        "report_dir": "biz_car_trends",
        "feeds_category": "biz_car",
        "references_file": "biz-car-trend-sources.md",
        "prompt_file": "biz-car-trend-scout.md",
    },
    "academic": {
        "report_dir": "academic_trends",
        "feeds_category": "academic",
        "references_file": "academic-scout-sources.md",
        "prompt_file": "academic-trend-scout.md",
    },
    "tech_events": {
        "report_dir": "tech_events",
        "feeds_category": "tech_events",
        "references_file": "tech-event-sources.md",
        "prompt_file": "tech-event-scout.md",
    },
    "lifestyle_events": {
        "report_dir": "lifestyle_events",
        "feeds_category": "lifestyle_events",
        "references_file": "lifestyle-event-sources.md",
        "prompt_file": "lifestyle-event-scout.md",
    },
}

EXCLUDED_DOMAINS: set[str] = {
    "notion.so", "github.com", "slack.com", "x.com", "twitter.com",
    "linkedin.com", "facebook.com", "instagram.com", "youtube.com",
}

EXCLUDED_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip",
}

# RSS探索パス（優先度順）
RSS_PATHS: list[str] = [
    "/feed", "/rss", "/atom.xml", "/feed.xml",
    "/index.xml", "/rss.xml", "/feed/",
    "/blog/feed", "/blog/rss", "/blog/atom.xml",
]

# ドメイン→サイト名の既知マッピング
KNOWN_SITE_NAMES: dict[str, str] = {
    "techcrunch.com": "TechCrunch",
    "arstechnica.com": "Ars Technica",
    "wired.com": "WIRED",
    "theverge.com": "The Verge",
    "engadget.com": "Engadget",
    "venturebeat.com": "VentureBeat",
    "www.osnews.com": "OSnews",
    "modal.com": "Modal",
    "www.cnn.com": "CNN",
    "techcommunity.microsoft.com": "Microsoft Tech Community",
}

DEFAULT_MAX_SITES = 10
DEFAULT_TIMEOUT = 10
DEFAULT_LOOKBACK_DAYS = 7

logger = get_logger("rss-source-updater")


# ─── ドメイン抽出・フィルタリング ─────────────────────────────────

def extract_domains_from_file(file_path: Path) -> set[str]:
    """ファイルからURLを抽出しドメイン集合を返す。"""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"ファイル読み込みエラー: {file_path} - {e}")
        return set()

    # Markdown link形式 + bare URL
    urls: set[str] = set()
    urls.update(re.findall(r'\[.*?\]\((https?://[^\)]+)\)', content))
    urls.update(re.findall(r'(?<!\()(https?://[^\s\)\]>]+)', content))

    domains: set[str] = set()
    for url in urls:
        domain = _get_domain(url)
        if not domain:
            continue
        if any(excl in domain for excl in EXCLUDED_DOMAINS):
            continue
        if any(url.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue
        domains.add(domain)

    return domains


def _get_domain(url: str) -> str:
    """URLからドメインを抽出する。"""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""


# ─── 既存ソース取得 ───────────────────────────────────────────────

def get_existing_sources() -> set[str]:
    """既存のFEEDS定義とreferencesファイルからドメイン集合を取得する。"""
    existing: set[str] = set()

    # fetch-rss-feeds.py から取得
    feeds_file = Path.home() / "scripts/rss/fetch-rss-feeds.py"
    if feeds_file.exists():
        try:
            content = feeds_file.read_text(encoding="utf-8")
            urls = re.findall(r'"url":\s*"(https?://[^"]+)"', content)
            for url in urls:
                domain = _get_domain(url)
                if domain:
                    existing.add(domain)
        except OSError as e:
            logger.warning(f"FEEDSファイル読み込みエラー: {e}")

    # references/*-sources.md から取得
    refs_dir = Path.home() / ".shared-ai/references"
    if refs_dir.exists():
        for ref_file in refs_dir.glob("*-sources.md"):
            try:
                content = ref_file.read_text(encoding="utf-8")
                # URLからドメイン抽出
                urls = re.findall(r'https?://[^\s\)\]>]+', content)
                for url in urls:
                    domain = _get_domain(url)
                    if domain:
                        existing.add(domain)
                # ドメイン名パターンも抽出
                domain_patterns = re.findall(
                    r'(?:^|\s)([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?'
                    r'\.[a-zA-Z]{2,})(?:\s|$)',
                    content,
                )
                existing.update(d.lower() for d in domain_patterns)
            except OSError:
                continue

    return existing


# ─── RSS探索 ─────────────────────────────────────────────────────

def find_rss_feed(domain: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """ドメインのRSS/Atomフィードを探索する。

    Args:
        domain: 探索対象ドメイン
        timeout: HTTPリクエストタイムアウト（秒）

    Returns:
        (feed_url, feed_type) のタプル。未発見時は ("", "")
    """
    # 既知パスを順に試行
    for path in RSS_PATHS:
        url = f"https://{domain}{path}"
        feed_type = _check_feed_url(url, timeout)
        if feed_type:
            return url, feed_type

    # HTMLページの<link>タグからRSSリンクを探索
    feed_url, feed_type = _find_feed_from_html(domain, timeout)
    if feed_url:
        return feed_url, feed_type

    return "", ""


def _check_feed_url(url: str, timeout: int) -> str:
    """URLがRSS/Atomフィードか確認する。フィードタイプを返す。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (RSS Feed Discovery)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return ""
            content_type = resp.headers.get("Content-Type", "").lower()
            if not any(ct in content_type for ct in ["xml", "rss", "atom"]):
                return ""
            content = resp.read().decode("utf-8", errors="replace")
            return _detect_feed_type(content)
    except Exception:
        return ""


def _find_feed_from_html(domain: str, timeout: int) -> tuple[str, str]:
    """HTMLページの<link>タグからRSS/Atomフィードを探索する。"""
    try:
        req = urllib.request.Request(f"https://{domain}", headers={
            "User-Agent": "Mozilla/5.0 (RSS Feed Discovery)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return "", ""
            content = resp.read().decode("utf-8", errors="replace")

        # RSS link
        rss_match = re.search(
            r'<link[^>]+type=["\']application/rss\+xml["\'][^>]+'
            r'href=["\']([^"\']+)["\']',
            content, re.IGNORECASE,
        )
        if not rss_match:
            # href が type より前にある場合
            rss_match = re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+'
                r'type=["\']application/rss\+xml["\']',
                content, re.IGNORECASE,
            )
        if rss_match:
            feed_url = _resolve_url(domain, rss_match.group(1))
            return feed_url, "rss"

        # Atom link
        atom_match = re.search(
            r'<link[^>]+type=["\']application/atom\+xml["\'][^>]+'
            r'href=["\']([^"\']+)["\']',
            content, re.IGNORECASE,
        )
        if not atom_match:
            atom_match = re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+'
                r'type=["\']application/atom\+xml["\']',
                content, re.IGNORECASE,
            )
        if atom_match:
            feed_url = _resolve_url(domain, atom_match.group(1))
            return feed_url, "atom"

    except Exception:
        pass

    return "", ""


def _resolve_url(domain: str, href: str) -> str:
    """相対URLを絶対URLに解決する。"""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return f"https:{href}"
    return f"https://{domain}{href}"


def _detect_feed_type(content: str) -> str:
    """XMLコンテンツからフィードタイプを判定する。空文字列=非フィード。"""
    try:
        root = ET.fromstring(content)
        tag = root.tag.lower()
        if "rss" in tag or "rdf" in tag:
            return "rss"
        if "feed" in tag or "atom" in tag:
            return "atom"
    except ET.ParseError:
        pass
    return ""


# ─── ファイル更新 ─────────────────────────────────────────────────

def get_site_name(domain: str) -> str:
    """ドメインからサイト名を推測する。"""
    if domain in KNOWN_SITE_NAMES:
        return KNOWN_SITE_NAMES[domain]
    # www. を除去してタイトルケース
    name = domain.removeprefix("www.")
    parts = name.split(".")
    if len(parts) >= 2:
        name = parts[0]
    return name.replace("-", " ").replace("_", " ").title()


def update_feeds_file(
    domain: str, rss_url: str, feed_type: str, category: str,
) -> bool:
    """fetch-rss-feeds.py のFEEDSリストにエントリを追加する。"""
    feeds_file = Path.home() / "scripts/rss/fetch-rss-feeds.py"
    if not feeds_file.exists():
        logger.warning(f"FEEDSファイルが見つかりません: {feeds_file}")
        return False

    try:
        content = feeds_file.read_text(encoding="utf-8")
        site_name = get_site_name(domain)

        # 既に登録済みか確認
        if rss_url in content:
            logger.info(f"既に登録済み: {rss_url}")
            return False

        # カテゴリセクションの最後の } の後に追加
        pattern = rf'("{category}": \[)(.*?)(\n    \],)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            logger.warning(f"カテゴリ '{category}' がFEEDSに見つかりません")
            return False

        new_entry = (
            f'        {{\n'
            f'            "name": "{site_name}",\n'
            f'            "url": "{rss_url}",\n'
            f'            "type": "{feed_type}",\n'
            f'        }},'
        )

        existing_feeds = match.group(2)
        last_brace = existing_feeds.rfind("}")
        if last_brace == -1:
            # 空のカテゴリ
            new_feeds = f"\n{new_entry}\n"
        else:
            new_feeds = (
                existing_feeds[:last_brace + 1]
                + "\n" + new_entry
                + existing_feeds[last_brace + 1:]
            )

        new_content = (
            content[:match.start()]
            + match.group(1) + new_feeds + match.group(3)
            + content[match.end():]
        )

        feeds_file.write_text(new_content, encoding="utf-8")
        return True

    except OSError as e:
        logger.error(f"FEEDSファイル更新エラー: {e}")
        return False


def update_references_file(domain: str, category_config: dict[str, str]) -> bool:
    """references/*-sources.md にサイトを追加する。"""
    ref_file = (
        Path.home() / ".shared-ai/references" / category_config["references_file"]
    )
    if not ref_file.exists():
        logger.warning(f"referencesファイルが見つかりません: {ref_file}")
        return False

    try:
        content = ref_file.read_text(encoding="utf-8")
        site_name = get_site_name(domain)

        # 既に含まれているか確認
        if domain in content or site_name in content:
            logger.info(f"既にreferencesに登録済み: {domain}")
            return False

        content = content.rstrip("\n") + f"\n- {site_name} ({domain})\n"
        ref_file.write_text(content, encoding="utf-8")
        return True

    except OSError as e:
        logger.error(f"referencesファイル更新エラー: {e}")
        return False


def update_prompt_file(
    site_name: str, category_config: dict[str, str], has_rss: bool,
) -> bool:
    """プロンプトファイルの事前取得済み/RSS未発見リストを更新する。"""
    prompt_file = (
        Path.home() / ".shared-ai/prompts" / category_config["prompt_file"]
    )
    if not prompt_file.exists():
        logger.warning(f"プロンプトファイルが見つかりません: {prompt_file}")
        return False

    try:
        content = prompt_file.read_text(encoding="utf-8")

        if site_name in content:
            return False

        if has_rss:
            pattern = r'(事前取得済み:.*?)(\n)'
        else:
            pattern = r'(RSSでカバーできないサイト(?:（検索で補完）)?:.*?)(\n)'

        match = re.search(pattern, content)
        if not match:
            return False

        new_content = content.replace(
            match.group(0),
            match.group(1) + f", {site_name}" + match.group(2),
        )
        prompt_file.write_text(new_content, encoding="utf-8")
        return True

    except OSError as e:
        logger.error(f"プロンプトファイル更新エラー: {e}")
        return False


# ─── レポートファイル探索 ─────────────────────────────────────────

def _detect_category_from_path(file_path: Path) -> str:
    """ファイルパスからカテゴリを推定する。"""
    path_str = str(file_path)
    for cat_key, config in CATEGORY_CONFIG.items():
        if config["report_dir"] in path_str:
            return cat_key
    return "tech"  # デフォルト


def get_report_files(
    base_date: str, categories: list[str], lookback_days: int,
) -> list[tuple[Path, str]]:
    """基準日から過去N日分のレポートファイルを取得する。

    Returns:
        (file_path, category_key) のリスト
    """
    base = datetime.strptime(base_date, "%Y-%m-%d")
    files: list[tuple[Path, str]] = []

    for i in range(lookback_days):
        date = base - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        for cat_key in categories:
            config = CATEGORY_CONFIG.get(cat_key)
            if not config:
                continue
            report_dir = config["report_dir"]
            file_path = (
                Path.home()
                / f"Documents/works/scout_reports/{report_dir}/daily"
                / f"{date_str}_{report_dir}.md"
            )
            if file_path.exists():
                files.append((file_path, cat_key))

    return files


# ─── メイン処理 ───────────────────────────────────────────────────

def main() -> None:
    """メインエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="レポートから未登録サイトを発見しRSS探索・ソース定義更新を行う",
    )
    parser.add_argument(
        "--date",
        help="基準日 (YYYY-MM-DD)。--domains 使用時は省略可",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=list(CATEGORY_CONFIG.keys()),
        default=list(CATEGORY_CONFIG.keys()),
        help="処理対象カテゴリ（デフォルト: 全カテゴリ）",
    )
    parser.add_argument(
        "--category",
        choices=list(CATEGORY_CONFIG.keys()),
        help="--domains 使用時の登録先カテゴリ",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="直接指定するレポートファイルパス（自動検出をスキップ）",
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        help="直接指定するドメインリスト（レポートからの抽出をスキップ）",
    )
    parser.add_argument(
        "--max-sites",
        type=int,
        default=DEFAULT_MAX_SITES,
        help=f"RSS探索する最大サイト数（デフォルト: {DEFAULT_MAX_SITES}）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTPリクエストタイムアウト秒（デフォルト: {DEFAULT_TIMEOUT}）",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"遡る日数（デフォルト: {DEFAULT_LOOKBACK_DAYS}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイル更新を行わず結果のみ表示する",
    )
    args = parser.parse_args()

    # 引数バリデーション
    if not args.domains and not args.files and not args.date:
        parser.error("--date, --files, --domains のいずれかが必要です")
    if args.domains and not args.category:
        parser.error("--domains 使用時は --category の指定が必要です")

    logger.info(f"RSS Source Updater 実行開始")

    # Step 1: 未登録ドメインの特定
    if args.domains:
        # 直接指定モード
        unregistered_domains = set(args.domains)
        category_map = {d: args.category for d in unregistered_domains}
        report_count = 0
        total_domains = len(unregistered_domains)
        logger.info(f"直接指定モード: {len(args.domains)}ドメイン")
    elif args.files:
        # ファイル直接指定モード
        report_files: list[tuple[Path, str]] = []
        for file_str in args.files:
            file_path = Path(file_str).expanduser()
            if not file_path.exists():
                logger.warning(f"ファイルが見つかりません: {file_path}")
                continue
            # パスからカテゴリを推定
            cat_key = _detect_category_from_path(file_path)
            report_files.append((file_path, cat_key))

        report_count = len(report_files)
        logger.info(f"ファイル直接指定モード: {report_count}件")

        if not report_files:
            result = {
                "success": True,
                "message": "処理対象ファイルなし",
                "report_count": 0,
                "rss_found": [],
                "rss_not_found": [],
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        # ドメイン抽出（カテゴリ紐付き）
        all_domains: set[str] = set()
        category_map: dict[str, str] = {}

        for file_path, cat_key in report_files:
            domains = extract_domains_from_file(file_path)
            for domain in domains:
                all_domains.add(domain)
                if domain not in category_map:
                    category_map[domain] = cat_key

        total_domains = len(all_domains)
        logger.info(f"抽出ドメイン: {total_domains}件")

        # 既存ソースとの差分
        existing = get_existing_sources()
        unregistered_domains = all_domains - existing
    else:
        # レポートスキャンモード
        report_files = get_report_files(
            args.date, args.categories, args.lookback_days,
        )
        report_count = len(report_files)
        logger.info(f"入力ファイル: {report_count}件")

        if not report_files:
            result = {
                "success": True,
                "message": "処理対象ファイルなし",
                "report_count": 0,
                "rss_found": [],
                "rss_not_found": [],
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        # ドメイン抽出（カテゴリ紐付き）
        all_domains: set[str] = set()
        category_map: dict[str, str] = {}

        for file_path, cat_key in report_files:
            domains = extract_domains_from_file(file_path)
            for domain in domains:
                all_domains.add(domain)
                if domain not in category_map:
                    category_map[domain] = cat_key

        total_domains = len(all_domains)
        logger.info(f"抽出ドメイン: {total_domains}件")

        # 既存ソースとの差分
        existing = get_existing_sources()
        unregistered_domains = all_domains - existing

    logger.info(f"未登録サイト: {len(unregistered_domains)}件")

    if not unregistered_domains:
        result = {
            "success": True,
            "message": "変更なし（全サイト登録済み）",
            "report_count": report_count,
            "total_domains": total_domains,
            "unregistered_count": 0,
            "rss_found": [],
            "rss_not_found": [],
        }
        print(json.dumps(result, ensure_ascii=False))
        return

    # Step 2: RSS探索
    rss_found: list[dict[str, str]] = []
    rss_not_found: list[dict[str, str]] = []

    targets = sorted(unregistered_domains)[:args.max_sites]
    for domain in targets:
        logger.info(f"RSS探索: {domain}...")
        rss_url, feed_type = find_rss_feed(domain, timeout=args.timeout)
        cat_key = category_map.get(domain, args.categories[0])
        site_name = get_site_name(domain)

        if rss_url:
            logger.info(f"   ✅ {feed_type}: {rss_url}")
            rss_found.append({
                "domain": domain,
                "site_name": site_name,
                "rss_url": rss_url,
                "feed_type": feed_type,
                "category": cat_key,
            })
        else:
            logger.info(f"   ❌ RSS未発見")
            rss_not_found.append({
                "domain": domain,
                "site_name": site_name,
                "category": cat_key,
            })

    # Step 3: ファイル更新（dry-run でなければ）
    updated_files: list[str] = []

    if not args.dry_run:
        for item in rss_found:
            cat_config = CATEGORY_CONFIG[item["category"]]
            if update_feeds_file(
                item["domain"], item["rss_url"],
                item["feed_type"], cat_config["feeds_category"],
            ):
                updated_files.append(
                    f"scripts/rss/fetch-rss-feeds.py (+{item['site_name']})"
                )
            update_prompt_file(item["site_name"], cat_config, has_rss=True)

        for item in rss_not_found:
            cat_config = CATEGORY_CONFIG[item["category"]]
            if update_references_file(item["domain"], cat_config):
                updated_files.append(
                    f".shared-ai/references/{cat_config['references_file']}"
                    f" (+{item['site_name']})"
                )
            update_prompt_file(item["site_name"], cat_config, has_rss=False)

    # Step 4: 結果出力
    result = {
        "success": True,
        "dry_run": args.dry_run,
        "base_date": args.date or "(direct)",
        "report_count": report_count,
        "total_domains": total_domains,
        "unregistered_count": len(unregistered_domains),
        "rss_found": rss_found,
        "rss_not_found": rss_not_found,
        "updated_files": updated_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
