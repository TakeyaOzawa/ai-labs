#!/bin/zsh
set -eu -o pipefail

# epoch-to-jst: Unix epochタイムスタンプをJST日時文字列に変換する
#
# 目的:
#   Unix epoch秒（小数点付き可）をJST（UTC+9）の日時文字列に変換する。
#   LLMによる日時計算の誤りを防ぐため、確実なシェルコマンドで変換する。
#   Slack ts、GitHub timestamp等あらゆるepoch値に対応。
#
# 使い方:
#   epoch-to-jst.sh <epoch値>
#   epoch-to-jst.sh <epoch値> [フォーマット]
#
# 例:
#   epoch-to-jst.sh 1778141160.296249
#   → 2026-05-07 17:06 JST
#
#   epoch-to-jst.sh 1778141160.296249 "%Y-%m-%d"
#   → 2026-05-07
#
#   epoch-to-jst.sh 1778141160 "%Y-%m-%d %H:%M:%S"
#   → 2026-05-07 17:06:00
#
# 入力: Unix epoch秒（整数または小数点付き）
# 出力: JST日時文字列（デフォルト: YYYY-MM-DD HH:MM JST）
# 依存: date (macOS)

if [[ $# -lt 1 ]]; then
  echo "Usage: slack-ts-to-jst.sh <slack_ts> [format]" >&2
  echo "Example: slack-ts-to-jst.sh 1778141160.296249" >&2
  exit 1
fi

TS="$1"
FORMAT="${2:-%Y-%m-%d %H:%M JST}"

# 小数点以下を除去（date -r は整数のみ受け付ける）
EPOCH="${TS%%.*}"

# 変換
TZ=Asia/Tokyo date -r "$EPOCH" "+$FORMAT"
