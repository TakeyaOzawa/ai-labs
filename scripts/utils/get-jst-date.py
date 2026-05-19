#!/usr/bin/env python3.12
"""
get-jst-date: JST基準の日付を取得する

目的:
    macOS/Linux共通で動作するJST日付取得スクリプト。
    LLMによる日付・曜日計算の誤りを防ぐため、確実なスクリプトで取得する。

使い方:
    python3.12 ~/scripts/get-jst-date.py                # 当日 (YYYY-MM-DD)
    python3.12 ~/scripts/get-jst-date.py --yesterday    # 前日
    python3.12 ~/scripts/get-jst-date.py --offset -1    # 1日前
    python3.12 ~/scripts/get-jst-date.py --offset -7    # 7日前
    python3.12 ~/scripts/get-jst-date.py --weekday      # 当日の曜日（月曜日〜日曜日）
    python3.12 ~/scripts/get-jst-date.py --yesterday --weekday  # 前日の曜日
    python3.12 ~/scripts/get-jst-date.py --date 2026-05-10 --weekday  # 指定日の曜日

出力: YYYY-MM-DD（デフォルト）または曜日文字列
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

from datetime import datetime, timedelta, timezone

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
WEEKDAY_JA = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    offset = 0
    show_weekday = False
    target_date_str: str | None = None

    i = 0
    while i < len(args):
        if args[i] == "--yesterday":
            offset = -1
        elif args[i] == "--offset":
            i += 1
            if i >= len(args):
                print("Error: --offset requires a number", file=sys.stderr)
                sys.exit(1)
            offset = int(args[i])
        elif args[i] == "--weekday":
            show_weekday = True
        elif args[i] == "--date":
            i += 1
            if i >= len(args):
                print("Error: --date requires YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
            target_date_str = args[i]
        elif args[i] in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{args[i]}'", file=sys.stderr)
            sys.exit(1)
        i += 1

    # 日付計算
    if target_date_str:
        target = datetime.strptime(target_date_str, "%Y-%m-%d").replace(
            tzinfo=JST
        ) + timedelta(days=offset)
    else:
        target = datetime.now(tz=JST) + timedelta(days=offset)

    if show_weekday:
        print(WEEKDAY_JA[target.weekday()])
    else:
        print(target.strftime("%Y-%m-%d"))



if __name__ == "__main__":
    main()
