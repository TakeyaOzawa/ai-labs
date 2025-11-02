#!/bin/bash

set -e

# Load environment variables from .env file if it exists
if [ -f "$(dirname "$0")/../.env" ]; then
    export $(cat "$(dirname "$0")/../.env" | grep -v '^#' | xargs)
fi

SLACK_TOKEN="${AMAZON_Q_SLACK_OAUTH_TOKEN}"
USER_ID="${AMAZON_Q_SLACK_USER_ID}"
TASK_SUMMARY="$1"
STATUS_DETAIL="$2"

if [ -z "$SLACK_TOKEN" ]; then
  echo "Error: AMAZON_Q_SLACK_OAUTH_TOKEN environment variable is not set"
  echo "Please set it in .env file or export AMAZON_Q_SLACK_OAUTH_TOKEN='xoxb-your-token'"
  exit 1
fi

if [ -z "$USER_ID" ]; then
  echo "Error: AMAZON_Q_SLACK_USER_ID environment variable is not set"
  echo "Please set it in .env file or export AMAZON_Q_SLACK_USER_ID='U1234567890'"
  exit 1
fi

if [ -z "$TASK_SUMMARY" ]; then
  echo "Error: Task summary is required"
  echo "Usage: $0 'Task summary' 'Status detail'"
  exit 1
fi

# デフォルトのステータス詳細（指定がない場合）
if [ -z "$STATUS_DETAIL" ]; then
  STATUS_DETAIL="確認が必要です"
fi

# JSONエスケープ処理
TASK_SUMMARY_ESCAPED=$(echo "$TASK_SUMMARY" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed 's/$/\\n/' | tr -d '\n' | sed 's/\\n$//')
STATUS_DETAIL_ESCAPED=$(echo "$STATUS_DETAIL" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed 's/$/\\n/' | tr -d '\n' | sed 's/\\n$//')

curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"channel\": \"$USER_ID\",
    \"text\": \"$TASK_SUMMARY_ESCAPED\",
    \"blocks\": [
      {
        \"type\": \"section\",
        \"text\": {
          \"type\": \"mrkdwn\",
          \"text\": \"*実施中のタスク:*\\n$TASK_SUMMARY_ESCAPED\"
        }
      },
      {
        \"type\": \"section\",
        \"text\": {
          \"type\": \"mrkdwn\",
          \"text\": \"*状況:*\\n$STATUS_DETAIL_ESCAPED\"
        }
      },
      {
        \"type\": \"divider\"
      }
    ]
  }"

echo ""
