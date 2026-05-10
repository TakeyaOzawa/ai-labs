#!/bin/zsh
set -eu -o pipefail

# create-daily-tasks: 日次scoutパイプラインのタスクファイルを生成する
#
# 目的:
#   日次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
#   タスクファイル（JSON）を生成する。
#
# 使い方:
#   create-daily-tasks.sh [基準日]
#
# 例:
#   create-daily-tasks.sh 2026-05-04
#
# 出力: JSON形式のタスクファイル（~/Documents/works/agent_histories/scout_daily/）
# 依存: npx (ulid), jq

BASE_DATE="${1:-$(TZ=Asia/Tokyo date -v-1d +%Y-%m-%d)}"
TASK_ID=$(npx --yes ulid 2>/dev/null)
NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
DIR="$HOME/Documents/works/agent_histories/scout_daily"

mkdir -p "$DIR"

# ─── 子タスクのULID生成 ──────────────────────────────────────────
CHILD_IDS=()
for i in {1..8}; do
  CHILD_IDS+=("$(npx --yes ulid 2>/dev/null)")
done

FILEPATH="${DIR}/${BASE_DATE}_${TASK_ID}_scout_daily.json"

cat > "$FILEPATH" << EOJSON
{
  "task_id": "${TASK_ID}",
  "task_name": "scout_daily",
  "args": {
    "base_date": "${BASE_DATE}"
  },
  "options": {
    "async": false,
    "timeout_seconds": 3600,
    "max_retries": 0,
    "retry_delay_seconds": 0
  },
  "status": "pending",
  "status_detail": null,
  "depends_on": null,
  "child_tasks": [
    {
      "task_id": "${CHILD_IDS[1]}",
      "task_name": "tech-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 300,
        "max_retries": 1,
        "retry_delay_seconds": 30
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[2]}",
      "task_name": "biz-car-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 300,
        "max_retries": 1,
        "retry_delay_seconds": 30
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[3]}",
      "task_name": "academic-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 300,
        "max_retries": 1,
        "retry_delay_seconds": 30
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[4]}",
      "task_name": "slack-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 600,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[5]}",
      "task_name": "gws-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 900,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[6]}",
      "task_name": "github-org-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 600,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[7]}",
      "task_name": "github-public-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 600,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[8]}",
      "task_name": "notion-trend-scout",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 900,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    }
  ],
  "created_at": "${NOW}",
  "updated_at": "${NOW}",
  "started_at": null,
  "completed_at": null,
  "error": null
}
EOJSON

echo "📋 日次scoutタスクファイルを作成しました"
echo "   タスクID: ${TASK_ID}"
echo "   タスク名: daily-scout"
echo "   基準日:   ${BASE_DATE}"
echo "   子タスク: 8件"
echo "   ファイル: ${FILEPATH}"
