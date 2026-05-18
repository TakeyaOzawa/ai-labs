#!/usr/bin/env python3.12
"""
slack-channel-collector: Slackチャンネルの日次メッセージを収集し中間ファイルを生成する

使い方:
    python3.12 scripts/slack-channel-collector.py \
        --channel C05B4AZ7ZMM \
        --channel-name エンジニア用 \
        --date 2026-05-16 \
        --output /path/to/output.md \
        --users-dir /path/to/slack_users/YYYY-MM-DD
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import urllib.request
import urllib.parse
import urllib.error

JST = timezone(timedelta(hours=9))

# ─── Slack API ──────────────────────────────────────────────────────────────

def slack_api(endpoint: str, params: dict, token: str) -> dict:
    """Slack APIを呼び出す。"""
    url = f"https://slack.com/api/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            print(f"  [WARN] Slack API error: {data.get('error', 'unknown')}", file=sys.stderr)
        return data
    except Exception as e:
        print(f"  [ERROR] API call failed: {e}", file=sys.stderr)
        return {"ok": False, "error": str(e)}


def get_channel_history(channel_id: str, oldest: float, latest: float, token: str) -> list[dict]:
    """チャンネル履歴を取得する（対象日のメッセージのみ）。"""
    messages = []
    cursor = None
    page = 0
    while True:
        params: dict = {
            "channel": channel_id,
            "oldest": str(oldest),
            "latest": str(latest),
            "limit": 200,
            "inclusive": "true",
        }
        if cursor:
            params["cursor"] = cursor
        data = slack_api("conversations.history", params, token)
        if not data.get("ok"):
            break
        new_msgs = data.get("messages", [])
        messages.extend(new_msgs)
        page += 1
        print(f"  [INFO] Page {page}: {len(new_msgs)} messages (total: {len(messages)})", file=sys.stderr)
        if not data.get("has_more") or not new_msgs:
            break
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.5)
    return messages


def get_thread_replies(channel_id: str, thread_ts: str, token: str) -> list[dict]:
    """スレッドの返信を取得する。"""
    data = slack_api("conversations.replies", {
        "channel": channel_id,
        "ts": thread_ts,
        "limit": 200,
    }, token)
    if not data.get("ok"):
        return []
    msgs = data.get("messages", [])
    return msgs[1:] if msgs else []  # 最初のメッセージは親メッセージなのでスキップ


def get_user_profile(user_id: str, token: str) -> dict:
    """ユーザープロフィールをAPIで取得する。"""
    data = slack_api("users.info", {"user": user_id}, token)
    if not data.get("ok"):
        return {}
    return data.get("user", {})


# ─── ユーザーID解決 ─────────────────────────────────────────────────────────

class UserResolver:
    def __init__(self, users_dir: Path, token: str):
        self.users_dir = users_dir
        self.token = token
        self.cache: dict[str, str] = {}
        self._user_data: str | None = None

    def _load_user_file(self, filepath: Path) -> str:
        if not filepath.exists():
            return ""
        try:
            return filepath.read_text(encoding="utf-8")
        except Exception:
            return ""

    def resolve(self, user_id: str) -> str:
        if not user_id:
            return "不明"
        if user_id in self.cache:
            return self.cache[user_id]

        # ローカルファイルから検索
        search_files = [
            "active/mdx.md", "active/dxm.md", "active/ms.md",
            "active/hr.md", "active/cp.md", "active/nyle-unset.md", "active/other.md",
        ]
        for fname in search_files:
            fpath = self.users_dir / fname
            content = self._load_user_file(fpath)
            if not content:
                continue
            # YAMLブロックでuser_idを検索
            pattern = rf"id:\s*{re.escape(user_id)}[\s\S]*?name:\s*(.+)"
            m = re.search(pattern, content)
            if m:
                name = m.group(1).strip().strip('"').strip("'")
                self.cache[user_id] = name
                return name
            # 逆パターン: name が先に来る場合
            pattern2 = rf"name:\s*(.+?)[\s\S]*?id:\s*{re.escape(user_id)}"
            # この正規表現は複雑になるので、シンプルなブロック検索にする
            # YAMLブロック分割でユーザーを探す
            blocks = re.split(r'\n(?=- id:|\n- id:)', content)
            for block in blocks:
                if user_id in block:
                    nm = re.search(r'name:\s*["\']?([^"\'\n]+)["\']?', block)
                    if nm:
                        name = nm.group(1).strip()
                        self.cache[user_id] = name
                        return name

        # APIで個別取得
        print(f"  [INFO] Resolving user {user_id} via API", file=sys.stderr)
        profile = get_user_profile(user_id, self.token)
        if profile:
            name = (profile.get("profile", {}).get("display_name") or
                    profile.get("profile", {}).get("real_name") or
                    profile.get("name") or user_id)
            self.cache[user_id] = name
            return name

        self.cache[user_id] = user_id
        return user_id


# ─── タイムスタンプ変換 ─────────────────────────────────────────────────────

def ts_to_jst(ts_str: str) -> str:
    """Slack tsをJST日時文字列に変換する。"""
    try:
        ts = float(ts_str)
        dt = datetime.fromtimestamp(ts, tz=JST)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts_str


def ts_to_date(ts_str: str) -> str:
    """Slack tsをJST日付文字列に変換する。"""
    try:
        ts = float(ts_str)
        dt = datetime.fromtimestamp(ts, tz=JST)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def ts_to_link_id(ts_str: str) -> str:
    """Slack tsをURL用ID（ドットなし）に変換する。"""
    return ts_str.replace(".", "")


def slack_link(channel_id: str, ts_str: str) -> str:
    """SlackメッセージのURLを生成する。"""
    return f"https://volare.slack.com/archives/{channel_id}/p{ts_to_link_id(ts_str)}"


# ─── リアクション解析 ───────────────────────────────────────────────────────

def format_reactions(reactions: list[dict]) -> str:
    """リアクションを表示形式に変換する。"""
    if not reactions:
        return "なし"
    parts = []
    for r in reactions:
        name = r.get("name", "")
        count = r.get("count", 0)
        parts.append(f":{name}:×{count}")
    return ", ".join(parts)


def is_high_attention(reactions: list[dict]) -> bool:
    """高注目かどうかを判定する。"""
    if not reactions:
        return False
    total = sum(r.get("count", 0) for r in reactions)
    types = len(reactions)
    return types >= 3 or total >= 5


# ─── メッセージフィルタリング ───────────────────────────────────────────────

def is_attendance(text: str) -> bool:
    """勤怠メッセージかどうかを判定する。"""
    keywords = ["出勤", "退勤", "休憩", "離席", "在席", "テレワーク", "リモート", "直行", "直帰",
                "おはようございます", "お疲れ様です", "お先に失礼", "よろしくお願いします。\n退勤"]
    for kw in keywords:
        if kw in text:
            return True
    return False


def is_system_bot(msg: dict) -> bool:
    """人間の反応のないシステム通知かどうかを判定する。"""
    if msg.get("subtype") != "bot_message":
        return False
    reactions = msg.get("reactions", [])
    reply_count = msg.get("reply_count", 0)
    return not reactions and reply_count == 0


def extract_links(text: str, attachments: list) -> list[str]:
    """メッセージからPR/Issue/NotionリンクをURL形式で抽出する。"""
    links = []
    # GitHub PRリンク
    pr_pattern = r'https://github\.com/[^\s<>|]+/pull/(\d+)'
    for m in re.finditer(pr_pattern, text):
        links.append(m.group(0))

    # attachmentsからもURL抽出（詳細テキストは無視）
    for att in attachments:
        title = att.get("title", "")
        title_link = att.get("title_link", "") or att.get("original_url", "")
        if title_link and title_link not in links:
            links.append(f"[{title}]({title_link})" if title else title_link)

    return links[:5]  # 最大5件


def clean_text(text: str) -> str:
    """テキストをクリーニングする（Slackの特殊記法を変換）。"""
    if not text:
        return ""
    # ユーザーメンション <@U...> → @user_id
    text = re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
    # チャンネルメンション <#C...> → #channel
    text = re.sub(r'<#([A-Z0-9]+)\|([^>]+)>', r'#\2', text)
    # リンク <URL|text> → text
    text = re.sub(r'<([^|>]+)\|([^>]+)>', r'\2', text)
    # リンク <URL> → URL
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
    # HTMLエンティティ
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 改行の正規化
    text = text.strip()
    # 長すぎる場合は切り詰め
    if len(text) > 500:
        text = text[:497] + "..."
    return text


# ─── レポート生成 ──────────────────────────────────────────────────────────

def generate_report(
    channel_id: str,
    channel_name: str,
    target_date: str,
    messages: list[dict],
    threads: dict[str, list[dict]],
    resolver: UserResolver,
) -> tuple[str, int, int, int]:
    """
    中間ファイルの内容を生成する。
    Returns: (content, message_count, thread_count, reply_count)
    """
    new_topics = []
    old_thread_updates = []
    unanswered = []

    msg_count = 0
    thread_count = 0
    reply_count = 0

    for msg in messages:
        ts = msg.get("ts", "")
        msg_date = ts_to_date(ts)

        # 勤怠・システム通知は除外
        text = msg.get("text", "")
        if is_attendance(text):
            continue
        if is_system_bot(msg):
            continue
        # join/leave subtypeは除外
        subtype = msg.get("subtype", "")
        if subtype in ("channel_join", "channel_leave", "channel_archive", "channel_purpose", "channel_topic"):
            continue

        msg_count += 1
        user_id = msg.get("user") or msg.get("username") or ""
        user_name = resolver.resolve(user_id) if user_id else "Bot"

        reactions = msg.get("reactions", [])
        reaction_str = format_reactions(reactions)
        reply_cnt = msg.get("reply_count", 0)

        attachments = msg.get("attachments", []) or []
        links = extract_links(text, attachments)
        links_str = " / ".join(links[:3]) if links else ""

        clean_t = clean_text(text)

        if reply_cnt > 0:
            thread_count += 1
            thread_replies = threads.get(ts, [])
            reply_count += len(thread_replies)

            # スレッドの結論を要約
            conclusion = "未決"
            if any(r.get("name") in ("sumi", "sumi1", "済", "済1", "済2", "done", "done2") for r in reactions):
                conclusion = "完了"
            elif thread_replies:
                last_reply = thread_replies[-1]
                last_text = clean_text(last_reply.get("text", ""))
                conclusion = f"最終返信: {last_text[:100]}"

            topic = f"""#### {clean_t[:80] or 'メッセージ'}

- **投稿**: [{ts}]({slack_link(channel_id, ts)})
- **投稿者**: {user_name}
- **投稿日時**: {ts_to_jst(ts)} JST
- **概要**: {clean_t[:200]}
- **返信数**: {reply_cnt}件
- **リアクション**: {reaction_str}{"" if not links_str else f"\n- **関連リンク**: {links_str}"}
- **スレッド結論**: {conclusion}
"""
            if thread_replies:
                topic += "\n<details><summary>スレッド返信</summary>\n\n"
                for rep in thread_replies[:10]:  # 最大10件
                    rep_user = resolver.resolve(rep.get("user", ""))
                    rep_text = clean_text(rep.get("text", ""))
                    rep_ts = rep.get("ts", "")
                    topic += f"  - **{rep_user}** ({ts_to_jst(rep_ts)}): {rep_text[:200]}\n"
                if len(thread_replies) > 10:
                    topic += f"  - ... 他{len(thread_replies) - 10}件\n"
                topic += "\n</details>\n"

            new_topics.append(topic)
        else:
            topic = f"""#### {clean_t[:80] or 'メッセージ'}

- **投稿**: [{ts}]({slack_link(channel_id, ts)})
- **投稿者**: {user_name}
- **投稿日時**: {ts_to_jst(ts)} JST
- **概要**: {clean_t[:200]}
- **返信数**: 0件
- **リアクション**: {reaction_str}{"" if not links_str else f"\n- **関連リンク**: {links_str}"}
"""
            new_topics.append(topic)

            # 未対応チェック
            if not reactions and not reply_cnt:
                unanswered.append({
                    "ts": ts,
                    "user": user_name,
                    "summary": clean_t[:100],
                })

    # レポートの構築
    lines = []

    if new_topics:
        lines.append("### 新規トピック\n")
        lines.extend(new_topics)

    if old_thread_updates:
        lines.append("### 過去スレッドへの返信\n")
        lines.extend(old_thread_updates)

    if unanswered:
        lines.append("### 未対応・要注意アイテム\n")
        lines.append("| 投稿 | 投稿者 | 概要 | リアクション | 返信数 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in unanswered:
            ts_link = f"[{item['ts']}]({slack_link(channel_id, item['ts'])})"
            lines.append(f"| {ts_link} | {item['user']} | {item['summary'][:80]} | なし | 0 |")
        lines.append("")

    body = "\n".join(lines) if lines else "対象日の投稿はありませんでした。\n"

    frontmatter = f"""---
date: {target_date}
channel_id: {channel_id}
channel_name: {channel_name}
collected_by: slack-trend-scout-channel
message_count: {msg_count}
thread_count: {thread_count}
reply_count: {reply_count}
---
"""
    content = frontmatter + "\n" + body
    return content, msg_count, thread_count, reply_count


# ─── メイン ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    parser.add_argument("--channel-name", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", required=True)
    parser.add_argument("--users-dir", required=True)
    args = parser.parse_args()

    token = os.environ.get("SLACK_REFERENCE_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_REFERENCE_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # 対象日の時刻範囲
    y, mo, d = map(int, args.date.split("-"))
    start_dt = datetime(y, mo, d, 0, 0, 0, tzinfo=JST)
    end_dt = datetime(y, mo, d, 23, 59, 59, tzinfo=JST)
    oldest = start_dt.timestamp()
    latest = end_dt.timestamp()

    print(f"  [INFO] Target: {args.channel_name} ({args.channel}) on {args.date}", file=sys.stderr)
    print(f"  [INFO] Epoch range: {oldest:.0f} - {latest:.0f}", file=sys.stderr)

    # ユーザーリゾルバ
    resolver = UserResolver(Path(args.users_dir), token)

    # チャンネル履歴取得
    messages = get_channel_history(args.channel, oldest, latest, token)
    print(f"  [INFO] Got {len(messages)} messages", file=sys.stderr)

    # スレッド返信の取得
    threads: dict[str, list[dict]] = {}
    for msg in messages:
        ts = msg.get("ts", "")
        reply_cnt = msg.get("reply_count", 0)
        if reply_cnt > 0:
            print(f"  [INFO] Fetching thread {ts} ({reply_cnt} replies)", file=sys.stderr)
            replies = get_thread_replies(args.channel, ts, token)
            if replies:
                threads[ts] = replies
            time.sleep(0.3)

    # レポート生成
    content, msg_count, thread_count, reply_count = generate_report(
        args.channel, args.channel_name, args.date,
        messages, threads, resolver,
    )

    # ファイル書き出し
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    print(f"✅ {args.channel_name} 完了")
    print(f"- 出力: {args.output}")
    print(f"- メッセージ数: {msg_count}")
    print(f"- スレッド数: {thread_count}")
    print(f"- 返信数: {reply_count}")


if __name__ == "__main__":
    main()
