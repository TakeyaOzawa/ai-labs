#!/usr/bin/env python3.12
"""
notify-slack: Markdownファイルまたはテキストを変換してSlackに投稿する

目的:
    各scoutエージェントやパイプラインから呼び出される汎用Slack通知スクリプト。
    Markdown→Slack mrkdwn変換、分割投稿、スレッド投稿をサポートする。
    従来のslack-notifierエージェントをスクリプト化し、コンテキスト消費を削減。

使い方:
    python3.12 scripts/notify-slack.py --file <path>
    python3.12 scripts/notify-slack.py --text "メッセージ"
    python3.12 scripts/notify-slack.py --file <path> --channel C05B4AZ7ZMM
    python3.12 scripts/notify-slack.py --file <path> --thread compact
    python3.12 scripts/notify-slack.py --file <path> --thread <thread_ts>

例:
    python3.12 scripts/notify-slack.py --file ~/Documents/works/scout_histories/2026-05-14_daily.md
    python3.12 scripts/notify-slack.py --file ~/Documents/works/scout_histories/2026-05-14_daily.md --channel C05B4AZ7ZMM
    python3.12 scripts/notify-slack.py --text "デプロイ完了" --channel C05B4AZ7ZMM --thread compact
    python3.12 scripts/notify-slack.py --text "追加情報" --thread 1715000000.000000

出力: JSON（成功/失敗情報）
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# ─── 定数定義 ────────────────────────────────────────────────────

DEFAULT_CHANNEL = "U076LRL1B35"
MAX_MESSAGE_LENGTH = 3800
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
TITLE_BAR_CHAR = "⎯"
TITLE_BAR_LENGTH = 20


# ─── Markdown → Slack mrkdwn 変換 ────────────────────────────────

def strip_frontmatter(text: str) -> str:
    """YAML frontmatter（---で囲まれた部分）を除去する。"""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip("\n")
    return text


def convert_md_to_mrkdwn(text: str) -> str:
    """MarkdownテキストをSlack mrkdwn形式に変換する。

    Args:
        text: Markdown形式のテキスト

    Returns:
        Slack mrkdwn形式に変換されたテキスト
    """
    text = strip_frontmatter(text)
    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        # コードブロック内はそのまま維持
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            # 言語指定を除去（```python → ```）
            if in_code_block:
                result.append("```")
            else:
                result.append("```")
            continue

        if in_code_block:
            result.append(line)
            continue

        # H1 → 装飾付きタイトルバー
        if line.startswith("# "):
            title = line[2:].strip()
            bar = TITLE_BAR_CHAR * TITLE_BAR_LENGTH
            result.append(bar)
            result.append("\u3000")
            result.append(f"*{title}*")
            result.append("\u3000")
            result.append(bar)
            continue

        # H2 → ■■ 見出し ■■
        if line.startswith("## "):
            heading = line[3:].strip()
            result.append(f"*■■ {heading} ■■*")
            continue

        # H3 → ◆ 見出し
        if line.startswith("### "):
            heading = line[4:].strip()
            result.append(f"*◆ {heading}*")
            continue

        # リンク変換: [text](url) → <url|text>
        line = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<\2|\1>',
            line
        )

        # 裸のURLはそのまま維持（unfurl_links=falseでプレビュー抑制）

        # 太字: **text** → *text*
        line = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', line)

        # リスト: - item → • item
        line = re.sub(r'^(\s*)- ', r'\1• ', line)

        result.append(line)

    converted = "\n".join(result)
    # 連続空行を2行以内に圧縮
    converted = re.sub(r'\n{3,}', '\n\n', converted)
    return converted


# ─── メッセージ分割 ──────────────────────────────────────────────

def split_message(text: str) -> list[str]:
    """テキストをSlackの文字数制限に合わせて分割する。

    セクション単位（見出しの手前）で分割し、各チャンクが
    MAX_MESSAGE_LENGTH以下になるようにする。

    Args:
        text: 変換済みのmrkdwnテキスト

    Returns:
        分割されたメッセージのリスト
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    # セクション区切りパターン（■■ or ◆ の手前）
    sections = re.split(r'(?=\*■■ |\*◆ )', text)
    chunks: list[str] = []
    current = ""

    for section in sections:
        if not section.strip():
            continue

        if len(current) + len(section) <= MAX_MESSAGE_LENGTH:
            current += section
        else:
            if current.strip():
                chunks.append(current.strip())
            # セクション自体が長すぎる場合は行単位で分割
            if len(section) > MAX_MESSAGE_LENGTH:
                lines = section.split("\n")
                current = ""
                for line in lines:
                    if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                        if current.strip():
                            chunks.append(current.strip())
                        current = line + "\n"
                    else:
                        current += line + "\n"
            else:
                current = section

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:MAX_MESSAGE_LENGTH]]


# ─── Slack API 呼び出し ──────────────────────────────────────────

def post_message(
    token: str,
    channel: str,
    text: str,
    thread_ts: str | None = None,
) -> dict:
    """Slack chat.postMessage APIを呼び出す。

    Args:
        token: Slack Bot Token（xoxb-...）
        channel: 投稿先チャンネルID or ユーザーID
        text: 投稿テキスト
        thread_ts: スレッドの親メッセージのタイムスタンプ（スレッド投稿時）

    Returns:
        APIレスポンスのdict

    Raises:
        SystemExit: リトライ超過時
    """
    payload: dict = {
        "channel": channel,
        "text": text,
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=data,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json; charset=utf-8")

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if not result.get("ok"):
                error = result.get("error", "unknown")
                print(f"Slack API error: {error}", file=sys.stderr)
                if error == "ratelimited":
                    retry_after = int(
                        resp.headers.get("Retry-After", "5")
                        if hasattr(resp, "headers") else "5"
                    )
                    time.sleep(retry_after + 1)
                    continue
                return result

            return result

        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", "5"))
                print(
                    f"  Rate limited. Waiting {retry_after}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(retry_after + 1)
                continue
            print(f"HTTP Error: {e.code} {e.reason}", file=sys.stderr)
            return {"ok": False, "error": f"http_{e.code}"}

        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "error": str(e.reason)}

    return {"ok": False, "error": "max_retries_exceeded"}


# ─── メイン処理 ──────────────────────────────────────────────────

def notify(
    token: str,
    channel: str,
    content: str,
    thread_mode: str | None,
) -> dict:
    """Slack通知のメインロジック。

    Args:
        token: Slack Bot Token
        channel: 投稿先チャンネルID
        content: 投稿するMarkdownコンテンツ
        thread_mode: スレッドモード（None/compact/thread_ts値）

    Returns:
        結果情報のdict
    """
    # Markdown → mrkdwn変換
    mrkdwn = convert_md_to_mrkdwn(content)

    # compactモード: H1タイトルバーを親メッセージ、残りをスレッドに分離
    if thread_mode == "compact":
        header_msg, body = _split_header(mrkdwn)
        if header_msg:
            # ヘッダーを親メッセージとして投稿
            result = post_message(token, channel, header_msg)
            if not result.get("ok"):
                return {
                    "success": False,
                    "error": result.get("error", "unknown"),
                    "posted_count": 0,
                }
            parent_ts = result.get("ts")
            # 残りの本文をスレッドに分割投稿
            chunks = split_message(body) if body.strip() else []
            posted_count = 1
            for i, chunk in enumerate(chunks):
                time.sleep(1)
                res = post_message(token, channel, chunk, parent_ts)
                if not res.get("ok"):
                    return {
                        "success": False,
                        "error": res.get("error", "unknown"),
                        "posted_count": posted_count,
                    }
                posted_count += 1
            return {
                "success": True,
                "posted_count": posted_count,
                "channel": channel,
                "thread_ts": parent_ts,
                "thread_mode": "compact",
            }
        # H1がない場合: 最初のチャンクを親メッセージ、残りをスレッドにぶら下げる
        chunks = split_message(mrkdwn)
        if chunks:
            result = post_message(token, channel, chunks[0])
            if not result.get("ok"):
                return {
                    "success": False,
                    "error": result.get("error", "unknown"),
                    "posted_count": 0,
                }
            parent_ts = result.get("ts")
            posted_count = 1
            for chunk in chunks[1:]:
                time.sleep(1)
                res = post_message(token, channel, chunk, parent_ts)
                if not res.get("ok"):
                    return {
                        "success": False,
                        "error": res.get("error", "unknown"),
                        "posted_count": posted_count,
                    }
                posted_count += 1
            return {
                "success": True,
                "posted_count": posted_count,
                "channel": channel,
                "thread_ts": parent_ts,
                "thread_mode": "compact",
            }

    # メッセージ分割
    chunks = split_message(mrkdwn)

    posted_count = 0
    first_ts: str | None = None
    thread_ts: str | None = None

    # スレッドモード判定（既存スレッドID指定）
    if thread_mode and thread_mode != "compact":
        thread_ts = thread_mode

    for i, chunk in enumerate(chunks):
        result = post_message(token, channel, chunk, thread_ts)

        if not result.get("ok"):
            return {
                "success": False,
                "error": result.get("error", "unknown"),
                "posted_count": posted_count,
            }

        posted_count += 1

        if i == 0 and not first_ts:
            first_ts = result.get("ts")

        # 投稿間隔（rate limit対策）
        if i < len(chunks) - 1:
            time.sleep(1)

    return {
        "success": True,
        "posted_count": posted_count,
        "channel": channel,
        "thread_ts": first_ts,
        "thread_mode": thread_mode or "sequential",
    }


def _split_header(mrkdwn: str) -> tuple[str, str]:
    """変換済みmrkdwnからH1タイトルバー部分と本文を分離する。

    H1タイトルバーは以下の形式:
        ⎯⎯⎯...
        　（全角スペース）
        *タイトル*
        　（全角スペース）
        ⎯⎯⎯...

    Returns:
        (ヘッダー文字列, 残りの本文) のタプル。H1がなければ ("", 元テキスト)
    """
    bar = TITLE_BAR_CHAR * TITLE_BAR_LENGTH
    lines = mrkdwn.split("\n")

    # 最初のタイトルバー開始位置を探す
    header_start = -1
    for i, line in enumerate(lines):
        if line.strip() == bar:
            header_start = i
            break

    if header_start == -1:
        return ("", mrkdwn)

    # タイトルバーの終了位置を探す（2つ目のbar）
    header_end = -1
    for i in range(header_start + 1, len(lines)):
        if lines[i].strip() == bar:
            header_end = i
            break

    if header_end == -1:
        return ("", mrkdwn)

    header_lines = lines[header_start:header_end + 1]
    # H1前のテキスト + H1後のテキストを本文として結合
    pre_header = lines[:header_start]
    post_header = lines[header_end + 1:]
    body_lines = pre_header + post_header

    header_msg = "\n".join(header_lines)
    body = "\n".join(body_lines).strip()

    return (header_msg, body)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Markdownファイルまたはテキストを変換してSlackに投稿する"
    )
    parser.add_argument(
        "--file", "-f",
        help="投稿内容のMarkdownファイルパス",
    )
    parser.add_argument(
        "--text", "-t",
        help="直接投稿するテキスト（--fileが無い場合に使用）",
    )
    parser.add_argument(
        "--channel", "-c",
        default=DEFAULT_CHANNEL,
        help=f"投稿先チャンネルID（デフォルト: {DEFAULT_CHANNEL}）",
    )
    parser.add_argument(
        "--thread",
        nargs="?",
        const="compact",
        default=None,
        help=(
            "スレッド投稿モード。"
            "引数なし or 'compact': H1タイトルを親メッセージにし残りをスレッドにぶら下げる"
            "（H1なしの場合は最初のチャンクが親）。"
            "thread_ts値: 指定スレッドに全メッセージを投稿"
        ),
    )
    parser.add_argument(
        "--token-env",
        default="MY_SLACK_OAUTH_TOKEN",
        help="Slack Bot Tokenの環境変数名（デフォルト: MY_SLACK_OAUTH_TOKEN）",
    )
    args = parser.parse_args()

    # 入力バリデーション
    if not args.file and not args.text:
        print(
            json.dumps(
                {"success": False, "error": "--file または --text が必要です"},
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    # トークン取得
    token = os.environ.get(args.token_env, "")
    if not token:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"環境変数 {args.token_env} が未設定です",
                },
                ensure_ascii=False,
            )
        )
        sys.exit(3)

    # コンテンツ取得
    if args.file:
        file_path = Path(args.file).expanduser()
        if not file_path.exists():
            print(
                json.dumps(
                    {"success": False, "error": f"ファイルが見つかりません: {file_path}"},
                    ensure_ascii=False,
                )
            )
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")
        source = str(file_path)
    else:
        content = args.text
        source = "直接テキスト"

    # 実行
    print(f"→ Slack通知開始: {source}", file=sys.stderr)
    print(f"  チャンネル: {args.channel}", file=sys.stderr)
    print(f"  スレッドモード: {args.thread or 'sequential'}", file=sys.stderr)

    result = notify(
        token=token,
        channel=args.channel,
        content=content,
        thread_mode=args.thread,
    )

    # 結果出力
    result["source"] = source
    print(json.dumps(result, ensure_ascii=False))

    if not result["success"]:
        sys.exit(1)


# ─── エントリポイント ────────────────────────────────────────────

from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
