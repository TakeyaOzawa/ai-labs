#!/bin/zsh
set -eu -o pipefail

# check-directory-freshness: ユーザーディレクトリの鮮度を確認する
#
# 目的:
#   Slack/Notionユーザーデータの日付ディレクトリが古くなっていないかを検知し、
#   更新が必要なタイミングを判定する。最終更新から指定日数以上経過していれば stale と判定。
#
# 使い方:
#   check-directory-freshness.sh --type slack --max-age-days 7
#   check-directory-freshness.sh --type notion --max-age-days 14
#
# 例:
#   check-directory-freshness.sh --type slack --max-age-days 7
#
# 出力: JSON形式

TYPE=""
MAX_AGE_DAYS=7

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type) TYPE="$2"; shift 2 ;;
    --max-age-days) MAX_AGE_DAYS="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TYPE" ]]; then
  echo '{"error": "--type is required (slack or notion)"}' 
  exit 1
fi

# ディレクトリパスの決定
case "$TYPE" in
  slack)
    BASE_DIR="${HOME}/Documents/works/slack_users"
    ;;
  notion)
    BASE_DIR="${HOME}/Documents/works/notion_users"
    ;;
  *)
    echo "{\"error\": \"Unknown type: ${TYPE}. Use 'slack' or 'notion'\"}"
    exit 1
    ;;
esac

# 最新の日付ディレクトリを特定
LATEST_DIR=$(ls -d "${BASE_DIR}"/20*/ 2>/dev/null | sort -r | head -1)

if [[ -z "$LATEST_DIR" ]]; then
  # ディレクトリが存在しない = 初回実行が必要
  echo "{\"stale\": true, \"type\": \"${TYPE}\", \"last_updated\": null, \"age_days\": 999, \"max_age_days\": ${MAX_AGE_DAYS}}"
  exit 0
fi

# ディレクトリ名から日付を抽出
LATEST_DATE=$(basename "$LATEST_DIR")
TODAY=$(TZ=Asia/Tokyo date +%Y-%m-%d)

# 日数差を計算
LATEST_EPOCH=$(date -j -f "%Y-%m-%d" "$LATEST_DATE" "+%s" 2>/dev/null || echo 0)
TODAY_EPOCH=$(date -j -f "%Y-%m-%d" "$TODAY" "+%s")
AGE_DAYS=$(( (TODAY_EPOCH - LATEST_EPOCH) / 86400 ))

if [[ $AGE_DAYS -ge $MAX_AGE_DAYS ]]; then
  STALE="true"
else
  STALE="false"
fi

echo "{\"stale\": ${STALE}, \"type\": \"${TYPE}\", \"last_updated\": \"${LATEST_DATE}\", \"age_days\": ${AGE_DAYS}, \"max_age_days\": ${MAX_AGE_DAYS}}"
