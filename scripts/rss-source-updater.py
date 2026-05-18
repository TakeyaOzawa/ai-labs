#!/usr/bin/env python3.12
"""
RSS Source Updater: trend/digestレポートから未登録サイトを発見し、RSS有無を調査してソース定義・プロンプトを自動更新

基準日から過去7日分のレポートを処理し、未登録サイトのRSS探索を行う。
"""

import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, List, Dict, Tuple
import xml.etree.ElementTree as ET


def get_target_files(base_date: str) -> List[Path]:
    """基準日から過去7日分のレポートファイルを取得"""
    base = datetime.strptime(base_date, "%Y-%m-%d")
    files = []
    
    for i in range(7):
        date = base - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        # tech_trends
        tech_file = Path.home() / f"Documents/works/scout_reports/tech_trends/daily/{date_str}_tech_trends.md"
        if tech_file.exists():
            files.append(tech_file)
        
        # biz_car_trends
        biz_file = Path.home() / f"Documents/works/scout_reports/biz_car_trends/daily/{date_str}_biz_car_trends.md"
        if biz_file.exists():
            files.append(biz_file)
        
        # academic_trends
        academic_file = Path.home() / f"Documents/works/scout_reports/academic_trends/daily/{date_str}_academic_trends.md"
        if academic_file.exists():
            files.append(academic_file)
    
    return files


def extract_urls_from_file(file_path: Path) -> Set[str]:
    """ファイルからURLを抽出"""
    urls = set()
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Markdown link形式: [text](url)
        markdown_links = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', content)
        urls.update(markdown_links)
        
        # bare URL形式: https://...
        bare_urls = re.findall(r'https?://[^\s\)]+', content)
        urls.update(bare_urls)
        
    except Exception as e:
        print(f"⚠️ ファイル読み込みエラー: {file_path} - {e}")
    
    return urls


def get_domain(url: str) -> str:
    """URLからドメインを抽出"""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""


def filter_urls(urls: Set[str]) -> Set[str]:
    """除外対象URLをフィルタリング"""
    filtered = set()
    exclude_domains = {
        'notion.so', 'github.com', 'slack.com', 'twitter.com', 'x.com',
        'linkedin.com', 'facebook.com', 'youtube.com', 'instagram.com'
    }
    exclude_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf'}
    
    for url in urls:
        domain = get_domain(url)
        
        # 除外ドメインチェック
        if any(excl in domain for excl in exclude_domains):
            continue
            
        # 画像URLチェック
        if any(url.lower().endswith(ext) for ext in exclude_extensions):
            continue
            
        # アンカーのみチェック
        if url.startswith('#'):
            continue
            
        filtered.add(url)
    
    return filtered


def get_existing_sources() -> Tuple[Set[str], Set[str]]:
    """既存のソース定義とFEEDSからドメインを取得"""
    
    # references/*-sources.mdから取得
    sources_domains = set()
    sources_files = [
        Path.home() / ".shared-ai/references/tech-trend-sources.md",
        Path.home() / ".shared-ai/references/biz-car-trend-sources.md", 
        Path.home() / ".shared-ai/references/academic-scout-sources.md",
        Path.home() / ".shared-ai/references/tech-event-sources.md",
        Path.home() / ".shared-ai/references/lifestyle-event-sources.md"
    ]
    
    for file_path in sources_files:
        if file_path.exists():
            try:
                content = file_path.read_text(encoding='utf-8')
                # URLを抽出してドメインに変換
                urls = re.findall(r'https?://[^\s\)]+', content)
                for url in urls:
                    domain = get_domain(url)
                    if domain:
                        sources_domains.add(domain)
            except Exception as e:
                print(f"⚠️ ソースファイル読み込みエラー: {file_path} - {e}")
    
    # fetch-rss-feeds.pyのFEEDSから取得
    feeds_domains = set()
    feeds_file = Path.home() / "scripts/fetch-rss-feeds.py"
    if feeds_file.exists():
        try:
            content = feeds_file.read_text(encoding='utf-8')
            # "url": "https://..." パターンを抽出
            urls = re.findall(r'"url":\s*"(https?://[^"]+)"', content)
            for url in urls:
                domain = get_domain(url)
                if domain:
                    feeds_domains.add(domain)
        except Exception as e:
            print(f"⚠️ FEEDSファイル読み込みエラー: {feeds_file} - {e}")
    
    return sources_domains, feeds_domains


def find_rss_feed(domain: str) -> Tuple[str, str]:
    """ドメインのRSS/Atomフィードを探索"""
    
    # 既知パターンのURL
    patterns = [
        f"https://{domain}/feed",
        f"https://{domain}/rss", 
        f"https://{domain}/atom.xml",
        f"https://{domain}/feed.xml",
        f"https://{domain}/index.xml",
        f"https://{domain}/rss.xml",
        f"https://{domain}/feed/",
        f"http://{domain}/feed",
        f"http://{domain}/rss"
    ]
    
    for url in patterns:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (RSS Feed Reader)"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '').lower()
                    if any(ct in content_type for ct in ['xml', 'rss', 'atom']):
                        # XMLとして解析してRSS/Atomか確認
                        content = resp.read().decode('utf-8', errors='replace')
                        if is_valid_feed(content):
                            feed_type = detect_feed_type(content)
                            return url, feed_type
        except Exception:
            continue
    
    # HTMLページの<link>タグを確認
    try:
        req = urllib.request.Request(f"https://{domain}", headers={
            "User-Agent": "Mozilla/5.0 (RSS Feed Reader)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                content = resp.read().decode('utf-8', errors='replace')
                # <link rel="alternate" type="application/rss+xml" href="...">
                rss_match = re.search(r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if rss_match:
                    feed_url = rss_match.group(1)
                    if not feed_url.startswith('http'):
                        feed_url = f"https://{domain}{feed_url}"
                    return feed_url, "rss"
                
                # <link rel="alternate" type="application/atom+xml" href="...">
                atom_match = re.search(r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/atom\+xml["\'][^>]+href=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if atom_match:
                    feed_url = atom_match.group(1)
                    if not feed_url.startswith('http'):
                        feed_url = f"https://{domain}{feed_url}"
                    return feed_url, "atom"
    except Exception:
        pass
    
    return "", ""


def is_valid_feed(content: str) -> bool:
    """XMLコンテンツがRSS/Atomフィードか確認"""
    try:
        root = ET.fromstring(content)
        # RSS
        if root.tag in ['rss', 'rdf:RDF'] or 'rss' in root.tag.lower():
            return True
        # Atom
        if root.tag.endswith('feed') or 'atom' in root.tag.lower():
            return True
    except:
        pass
    return False


def detect_feed_type(content: str) -> str:
    """フィードタイプ（rss/atom）を判定"""
    try:
        root = ET.fromstring(content)
        if root.tag.endswith('feed') or 'atom' in root.tag.lower():
            return "atom"
        else:
            return "rss"
    except:
        return "rss"


def get_site_name(domain: str) -> str:
    """ドメインからサイト名を推測"""
    # 簡単な変換ルール
    name_map = {
        'techcrunch.com': 'TechCrunch',
        'arstechnica.com': 'Ars Technica', 
        'wired.com': 'WIRED',
        'theverge.com': 'The Verge',
        'engadget.com': 'Engadget',
        'venturebeat.com': 'VentureBeat'
    }
    
    if domain in name_map:
        return name_map[domain]
    
    # ドメインから推測
    parts = domain.split('.')
    if len(parts) >= 2:
        name = parts[-2]  # example.com -> example
        return name.replace('-', ' ').replace('_', ' ').title()
    
    return domain


def determine_category(file_path: Path) -> str:
    """ファイルパスからカテゴリを判定"""
    path_str = str(file_path)
    
    if 'tech_trends' in path_str:
        return 'tech'
    elif 'biz_car_trends' in path_str:
        return 'biz_car'
    elif 'academic_trends' in path_str:
        return 'academic'
    elif 'tech_events' in path_str:
        return 'tech_events'
    elif 'lifestyle_events' in path_str:
        return 'lifestyle_events'
    
    return 'tech'  # デフォルト


def update_feeds_file(domain: str, rss_url: str, feed_type: str, category: str):
    """fetch-rss-feeds.pyのFEEDSリストに追記"""
    feeds_file = Path.home() / "scripts/fetch-rss-feeds.py"
    
    if not feeds_file.exists():
        print(f"⚠️ FEEDSファイルが見つかりません: {feeds_file}")
        return
    
    try:
        content = feeds_file.read_text(encoding='utf-8')
        site_name = get_site_name(domain)
        
        # 該当カテゴリの最後の}の前に追加
        new_entry = f'''        {{
            "name": "{site_name}",
            "url": "{rss_url}",
            "type": "{feed_type}",
        }},'''
        
        # カテゴリセクションを見つけて追記
        category_pattern = f'"{category}": \\[(.*?)\\],'
        match = re.search(category_pattern, content, re.DOTALL)
        
        if match:
            # 最後の}の前に追加
            category_content = match.group(1)
            last_brace_pos = category_content.rfind('}')
            if last_brace_pos != -1:
                new_category_content = category_content[:last_brace_pos+1] + '\n' + new_entry + category_content[last_brace_pos+1:]
                new_content = content.replace(match.group(1), new_category_content)
                
                feeds_file.write_text(new_content, encoding='utf-8')
                print(f"✅ FEEDS追加: {site_name} ({rss_url}) → カテゴリ: {category}")
        else:
            print(f"⚠️ カテゴリ '{category}' がFEEDSファイルに見つかりません")
            
    except Exception as e:
        print(f"⚠️ FEEDSファイル更新エラー: {e}")


def update_sources_file(domain: str, category: str):
    """references/*-sources.mdファイルに追記"""
    
    # カテゴリマッピング
    sources_files = {
        'tech': Path.home() / ".shared-ai/references/tech-trend-sources.md",
        'biz_car': Path.home() / ".shared-ai/references/biz-car-trend-sources.md",
        'academic': Path.home() / ".shared-ai/references/academic-scout-sources.md",
        'tech_events': Path.home() / ".shared-ai/references/tech-event-sources.md",
        'lifestyle_events': Path.home() / ".shared-ai/references/lifestyle-event-sources.md"
    }
    
    sources_file = sources_files.get(category)
    if not sources_file or not sources_file.exists():
        print(f"⚠️ ソースファイルが見つかりません: {sources_file}")
        return
    
    try:
        content = sources_file.read_text(encoding='utf-8')
        site_name = get_site_name(domain)
        
        # 適切なセクションに追加（簡易実装：末尾に追加）
        content += f"\n{site_name}"
        
        sources_file.write_text(content, encoding='utf-8')
        print(f"✅ references追加: {site_name} → カテゴリ: {category}")
        
    except Exception as e:
        print(f"⚠️ ソースファイル更新エラー: {e}")


def update_prompt_file(site_name: str, category: str, has_rss: bool):
    """プロンプトファイルの「事前取得済み」または「RSSでカバーできないサイト」行に追加"""
    
    # カテゴリマッピング
    prompt_files = {
        'tech': Path.home() / ".shared-ai/prompts/tech-trend-scout.md",
        'biz_car': Path.home() / ".shared-ai/prompts/biz-car-trend-scout.md",
        'academic': Path.home() / ".shared-ai/prompts/academic-trend-scout.md",
        'tech_events': Path.home() / ".shared-ai/prompts/tech-event-scout.md",
        'lifestyle_events': Path.home() / ".shared-ai/prompts/lifestyle-event-scout.md"
    }
    
    prompt_file = prompt_files.get(category)
    if not prompt_file or not prompt_file.exists():
        print(f"⚠️ プロンプトファイルが見つかりません: {prompt_file}")
        return
    
    try:
        content = prompt_file.read_text(encoding='utf-8')
        
        if has_rss:
            # 「事前取得済み:」行に追加
            pattern = r'(事前取得済み:.*?)(\n)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                new_line = match.group(1) + f", {site_name}" + match.group(2)
                content = content.replace(match.group(0), new_line)
        else:
            # 「RSSでカバーできないサイト（検索で補完）:」行に追加
            pattern = r'(RSSでカバーできないサイト（検索で補完）:.*?)(\n)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                new_line = match.group(1) + f", {site_name}" + match.group(2)
                content = content.replace(match.group(0), new_line)
        
        prompt_file.write_text(content, encoding='utf-8')
        
    except Exception as e:
        print(f"⚠️ プロンプトファイル更新エラー: {e}")


def main():
    if len(sys.argv) != 2:
        print("使用方法: python3.12 scripts/rss-source-updater.py <基準日 YYYY-MM-DD>")
        sys.exit(1)
    
    base_date = sys.argv[1]
    
    print(f"📡 RSS Source Updater 実行開始（基準日: {base_date}）")
    
    # Step 1: 入力ファイル取得
    target_files = get_target_files(base_date)
    print(f"入力ファイル: {len(target_files)}件")
    
    if not target_files:
        print("⚠️ 処理対象ファイルがありません")
        return
    
    # Step 2: URL抽出
    all_urls = set()
    for file_path in target_files:
        urls = extract_urls_from_file(file_path)
        all_urls.update(urls)
    
    # フィルタリング
    filtered_urls = filter_urls(all_urls)
    
    # ドメイン単位で重複排除
    domains = set()
    for url in filtered_urls:
        domain = get_domain(url)
        if domain:
            domains.add(domain)
    
    print(f"抽出URL: {len(domains)}ドメイン")
    
    # Step 3: 既存ソース確認
    sources_domains, feeds_domains = get_existing_sources()
    
    # Step 4: 未登録サイト特定
    unregistered_domains = domains - sources_domains - feeds_domains
    print(f"未登録サイト: {len(unregistered_domains)}件")
    
    if not unregistered_domains:
        print("⏭️ 変更なし（全サイト登録済み）")
        return
    
    # Step 5: RSS探索（最大10サイト）
    rss_found = []
    rss_not_found = []
    
    for i, domain in enumerate(list(unregistered_domains)[:10]):
        print(f"  → RSS探索: {domain}...", end=" ")
        
        rss_url, feed_type = find_rss_feed(domain)
        
        if rss_url:
            rss_found.append((domain, rss_url, feed_type))
            print(f"✅ {feed_type}: {rss_url}")
        else:
            rss_not_found.append(domain)
            print("❌ 未発見")
    
    # Step 6: 更新実行
    for domain, rss_url, feed_type in rss_found:
        # カテゴリ判定（最初に見つかったファイルから）
        category = 'tech'  # デフォルト
        for file_path in target_files:
            if any(get_domain(url) == domain for url in extract_urls_from_file(file_path)):
                category = determine_category(file_path)
                break
        
        site_name = get_site_name(domain)
        update_feeds_file(domain, rss_url, feed_type, category)
        update_prompt_file(site_name, category, True)
    
    for domain in rss_not_found:
        # カテゴリ判定
        category = 'tech'  # デフォルト
        for file_path in target_files:
            if any(get_domain(url) == domain for url in extract_urls_from_file(file_path)):
                category = determine_category(file_path)
                break
        
        site_name = get_site_name(domain)
        update_sources_file(domain, category)
        update_prompt_file(site_name, category, False)
    
    # Step 7: ログ出力
    print(f"\n📡 RSS Source Updater 実行結果（基準日: {base_date}）")
    print(f"入力ファイル: {len(target_files)}件")
    print(f"抽出URL: {len(domains)}ドメイン")
    print(f"未登録サイト: {len(unregistered_domains)}件")
    print()
    
    if rss_found:
        print("✅ RSS発見 → FEEDS追加:")
        for domain, rss_url, feed_type in rss_found:
            site_name = get_site_name(domain)
            print(f"  - {site_name} ({rss_url}) → カテゴリ: tech")
        print()
    
    if rss_not_found:
        print("📝 RSS未発見 → references追加:")
        for domain in rss_not_found:
            site_name = get_site_name(domain)
            print(f"  - {site_name} → カテゴリ: tech")
        print()


if __name__ == "__main__":
    main()
