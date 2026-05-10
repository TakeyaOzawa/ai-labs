#!/usr/bin/env python3.12
"""
epoch-to-jst: Unix epochタイムスタンプをJST日時文字列に変換する

目的:
    Unix epoch秒（小数点付き可）をJST（UTC+9）の日時文字列に変換する。
    LLMによる日時計算の誤りを防ぐため、確実なスクリプトで変換する。
    Slack ts、GitHub timestamp等あらゆるepoch値に対応。

使い方:
    python3.12 scripts/epoch-to-jst.py <epoch値> [フォーマット]

例:
    python3.12 scripts/epoch-to-jst.py 1778141160.296249
    → 2026-05-07 17:06 JST

    python3.12 scripts/epoch-to-jst.py 1778141160.296249 "%Y-%m-%d"
    → 2026-05-07

    python3.12 scripts/epoch-to-jst.py 1778141160 "%Y-%m-%d %H:%M:%S"
    → 2026-05-07 17:06:00

出力: JST日時文字列（デフォルト: YYYY-MM-DD HH:MM JST）
"""

import sys
from datetime import datetime, timedelta, timezone

# ─── 定数 ────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))
DEFAULT_FORMAT = "%Y-%m-%d %H:%M JST"


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: epoch-to-jst.py <epoch> [format]", file=sys.stderr)
        print("Example: epoch-to-jst.py 1778141160.296249", file=sys.stderr)
        sys.exit(1)

    ts = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_FORMAT

    # 小数点付きepochに対応
    epoch = float(ts)
    dt = datetime.fromtimestamp(epoch, tz=JST)
    print(dt.strftime(fmt))



from _version_check import check_python_version

if __name__ == "__main__":
    check_python_version()
    main()
