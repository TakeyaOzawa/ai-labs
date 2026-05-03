#!/usr/bin/env python3
"""
Slack APIから全ユーザーを取得し、1つのJSONファイルとして保存する。

使い方:
  SLACK_BOT_TOKEN=xoxb-... python3 scripts/fetch-slack-users.py <output_dir>

引数:
  output_dir: JSONファイルの保存先ディレクトリ（all_users.json として出力）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error


def fetch_all_users(token: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    cursor = ""
    batch_num = 0
    all_members = []

    while True:
        batch_num += 1
        url = "https://slack.com/api/users.list?limit=200"
        if cursor:
            url += f"&cursor={cursor}"

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json; charset=utf-8")

        max_retries = 5
        data = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_after = int(e.headers.get("Retry-After", 30))
                    print(f"  Rate limited. Waiting {retry_after}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(retry_after + 1)
                    req = urllib.request.Request(url)
                    req.add_header("Authorization", f"Bearer {token}")
                    req.add_header("Content-Type", "application/json; charset=utf-8")
                    continue
                print(f"Error fetching page {batch_num}: {e}")
                sys.exit(1)
            except urllib.error.URLError as e:
                print(f"Error fetching page {batch_num}: {e}")
                sys.exit(1)
        else:
            print(f"Failed after {max_retries} retries for page {batch_num}")
            sys.exit(1)

        if not data.get("ok"):
            print(f"API error: {data.get('error', 'unknown')}")
            sys.exit(1)

        members = data.get("members", [])
        all_members.extend(members)
        print(f"Page {batch_num}: +{len(members)} members (total: {len(all_members)})")

        next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not next_cursor:
            break
        cursor = next_cursor

    # 全件を1ファイルに保存
    output_file = os.path.join(output_dir, "all_users.json")
    with open(output_file, "w") as f:
        json.dump(all_members, f, ensure_ascii=False)

    print(f"\nSaved {len(all_members)} members -> {output_file}")
    return len(all_members)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <output_dir>")
        sys.exit(1)

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable is required")
        sys.exit(1)

    output_dir = sys.argv[1]
    fetch_all_users(token, output_dir)


if __name__ == "__main__":
    main()
