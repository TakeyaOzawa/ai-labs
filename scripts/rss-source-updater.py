#!/usr/bin/env python3.12
import re
import urllib.request
import urllib.parse
from pathlib import Path
from collections import defaultdict

def extract_urls_from_md(file_path):
    """MarkdownファイルからURLを抽出"""
    urls = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Markdown link形式: [text](url)
        md_links = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', content)
        urls.update(md_links)
        
        # bare URL形式: https://...
        bare_urls = re.findall(r'https?://[^\s\)]+', content)
        urls.update(bare_urls)
        
    except Exception as e:
        print(f"ファイル読み込みエラー: {file_path} - {e}")
    
    return urls

def get_domain(url):
    """URLからドメインを抽出"""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    except:
        return None

def filter_urls(urls):
    """除外対象URLをフィルタ"""
    exclude_domains = {'notion.so', 'github.com', 'slack.com'}
    exclude_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg'}
    
    filtered = set()
    for url in urls:
        domain = get_domain(url)
        if not domain or domain in exclude_domains:
            continue
        if any(url.lower().endswith(ext) for ext in exclude_extensions):
            continue
        if url.startswith('#'):
            continue
        filtered.add(url)
    
    return filtered

def get_existing_domains():
    """既存のソース定義からドメインを取得"""
    domains = set()
    
    # fetch-rss-feeds.pyから取得
    feeds_file = Path.home() / 'scripts/fetch-rss-feeds.py'
    if feeds_file.exists():
        with open(feeds_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 全カテゴリのURLを抽出
        url_matches = re.findall(r'"url":\s*"([^"]+)"', content)
        for url in url_matches:
            domain = get_domain(url)
            if domain:
                domains.add(domain)
    
    return domains

def check_rss_feed(domain):
    """ドメインでRSS/Atomフィードを探索"""
    common_paths = ['/feed', '/rss', '/atom.xml', '/feed.xml', '/index.xml', '/rss.xml', '/feed/']
    
    for path in common_paths:
        url = f"https://{domain}{path}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'xml' in content_type or 'rss' in content_type or 'atom' in content_type:
                        # XMLの内容を確認
                        content = resp.read().decode('utf-8', errors='ignore')[:1000]
                        if '<rss' in content or '<feed' in content:
                            feed_type = 'atom' if '<feed' in content else 'rss'
                            return url, feed_type
        except:
            continue
    
    # HTMLページのlinkタグを確認
    try:
        req = urllib.request.Request(f"https://{domain}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')[:5000]
            
            # RSS/Atomのlinkタグを探す
            rss_match = re.search(r'<link[^>]*type=["\']application/rss\+xml["\'][^>]*href=["\']([^"\']+)["\']', content, re.I)
            atom_match = re.search(r'<link[^>]*type=["\']application/atom\+xml["\'][^>]*href=["\']([^"\']+)["\']', content, re.I)
            
            if rss_match:
                feed_url = rss_match.group(1)
                if not feed_url.startswith('http'):
                    feed_url = f"https://{domain}{feed_url}"
                return feed_url, 'rss'
            elif atom_match:
                feed_url = atom_match.group(1)
                if not feed_url.startswith('http'):
                    feed_url = f"https://{domain}{feed_url}"
                return feed_url, 'atom'
    except:
        pass
    
    return None, None

def update_feeds_file(category, site_name, feed_url, feed_type):
    """fetch-rss-feeds.pyのFEEDS辞書に追加"""
    feeds_file = Path.home() / 'scripts/fetch-rss-feeds.py'
    
    with open(feeds_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 該当カテゴリのセクションを見つけて追加
    new_entry = f'        {{\n            "name": "{site_name}",\n            "url": "{feed_url}",\n            "type": "{feed_type}",\n        }},'
    
    # カテゴリの終了位置を見つけて挿入
    pattern = f'"{category}": \[(.*?)\],'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        category_content = match.group(1)
        # 最後のエントリの後に追加
        updated_content = category_content.rstrip() + '\n' + new_entry + '\n    '
        new_content = content.replace(match.group(1), updated_content)
        
        with open(feeds_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    return False

def update_references_file(category, site_name):
    """referencesファイルに追加"""
    ref_files = {
        'tech': 'tech-trend-sources.md',
        'biz_car': 'biz-car-trend-sources.md', 
        'academic': 'academic-scout-sources.md'
    }
    
    if category not in ref_files:
        return False
    
    ref_file = Path.home() / '.shared-ai/references' / ref_files[category]
    
    if ref_file.exists():
        with open(ref_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 適切なセクションに追加（簡易実装）
        content += f"\n{site_name}"
        
        with open(ref_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    return False

def main():
    base_date = "2026-05-10"
    dates = ["2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-10"]
    
    categories = {
        'tech_trends': 'tech',
        'biz_car_trends': 'biz_car', 
        'academic_trends': 'academic'
    }
    
    print(f"📡 RSS Source Updater 実行結果（基準日: {base_date}）")
    
    total_files = 0
    total_urls = 0
    rss_found = []
    rss_not_found = []
    
    # 既存ドメインを取得
    existing_domains = get_existing_domains()
    print(f"既存登録ドメイン数: {len(existing_domains)}")
    
    for trend_type, category in categories.items():
        print(f"\n=== {category} カテゴリ処理中 ===")
        
        # ファイル収集
        files = []
        for date in dates:
            file_path = Path.home() / f"Documents/works/scout_histories/{trend_type}/daily/{date}_{trend_type}.md"
            if file_path.exists():
                files.append(file_path)
        
        if not files:
            print(f"  対象ファイルなし")
            continue
        
        total_files += len(files)
        print(f"  入力ファイル: {len(files)}件")
        
        # URL抽出
        all_urls = set()
        for file_path in files:
            urls = extract_urls_from_md(file_path)
            all_urls.update(urls)
        
        filtered_urls = filter_urls(all_urls)
        domains = {get_domain(url) for url in filtered_urls if get_domain(url)}
        
        print(f"  抽出URL: {len(domains)}ドメイン")
        total_urls += len(domains)
        
        # 未登録ドメインを特定
        new_domains = domains - existing_domains
        
        print(f"  未登録サイト: {len(new_domains)}件")
        
        if not new_domains:
            print(f"  ⏭️ 変更なし（全サイト登録済み）")
            continue
        
        # RSS探索（最大5サイト）
        check_count = 0
        for domain in list(new_domains)[:5]:
            if check_count >= 5:
                break
            
            print(f"    RSS探索: {domain}...", end=" ")
            feed_url, feed_type = check_rss_feed(domain)
            
            if feed_url:
                print(f"✅ {feed_type}")
                rss_found.append({
                    'domain': domain,
                    'feed_url': feed_url,
                    'feed_type': feed_type,
                    'category': category
                })
            else:
                print("❌")
                rss_not_found.append({
                    'domain': domain,
                    'category': category
                })
            
            check_count += 1
    
    # 結果サマリー
    print(f"\n入力ファイル: {total_files}件")
    print(f"抽出URL: {total_urls}ドメイン")
    print(f"未登録サイト: {len(rss_found) + len(rss_not_found)}件")
    
    if rss_found:
        print(f"\n✅ RSS発見 → FEEDS追加:")
        for item in rss_found:
            print(f"  - {item['domain']} ({item['feed_url']}) → カテゴリ: {item['category']}")
    
    if rss_not_found:
        print(f"\n📝 RSS未発見 → references追加:")
        for item in rss_not_found:
            print(f"  - {item['domain']} → カテゴリ: {item['category']}")
    
    if not rss_found and not rss_not_found:
        print(f"\n⏭️ 変更なし（全サイト登録済み）")

if __name__ == "__main__":
    main()
