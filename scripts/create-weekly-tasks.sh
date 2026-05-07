#!/bin/zsh
set -eu -o pipefail

# create-weekly-tasks: 週次scoutパイプラインのタスクファイルを生成する
#
# 目的:
#   週次scoutパイプライン実行前に、各エージェントの実行状態を追跡するための
#   タスクファイル（JSON）を生成する。イベント系RSSフィードの事前取得も行う。
#
# 使い方:
#   create-weekly-tasks.sh [基準日]
#
# 例:
#   create-weekly-tasks.sh 2026-05-04
#
# 出力: JSON形式のタスクファイル（~/Documents/works/agent_histories/scout_weekly/）
# 依存: npx (ulid), python3 (fetch-rss-feeds.py)

BASE_DATE="${1:-$(TZ=Asia/Tokyo date -v-1d +%Y-%m-%d)}"
TASK_ID=$(npx --yes ulid 2>/dev/null)
NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
DIR="$HOME/Documents/works/agent_histories/scout_weekly"

mkdir -p "$DIR"

# 子タスクのULIDを事前生成
CHILD_IDS=()
for i in {1..9}; do
  CHILD_IDS+=("$(npx --yes ulid 2>/dev/null)")
done

FILEPATH="${DIR}/${BASE_DATE}_${TASK_ID}_scout_weekly.json"

cat > "$FILEPATH" << EOJSON
{
  "task_id": "${TASK_ID}",
  "task_name": "scout_weekly",
  "args": {
    "base_date": "${BASE_DATE}"
  },
  "options": {
    "async": false,
    "timeout_seconds": 7200,
    "max_retries": 0,
    "retry_delay_seconds": 0
  },
  "status": "pending",
  "status_detail": null,
  "depends_on": null,
  "child_tasks": [
    {
      "task_id": "${CHILD_IDS[1]}",
      "task_name": "slack-digest-scout",
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
      "task_id": "${CHILD_IDS[2]}",
      "task_name": "gws-digest-scout",
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
      "task_id": "${CHILD_IDS[3]}",
      "task_name": "tech-event-scout",
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
      "task_name": "lifestyle-event-scout",
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
      "task_id": "${CHILD_IDS[5]}",
      "task_name": "tech-blog-material-scout",
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
      "task_id": "${CHILD_IDS[6]}",
      "task_name": "tech-blog-planner",
      "args": {
        "base_date": "${BASE_DATE}"
      },
      "options": {
        "async": true,
        "timeout_seconds": 900,
        "max_retries": 1,
        "retry_delay_seconds": 60
      },
      "status": "pending",
      "status_detail": null,
      "depends_on": "tech-blog-material-scout",
      "child_tasks": [],
      "created_at": "${NOW}",
      "updated_at": "${NOW}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "task_id": "${CHILD_IDS[7]}",
      "task_name": "github-org-digest-scout",
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
      "task_name": "github-public-digest-scout",
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
      "task_id": "${CHILD_IDS[9]}",
      "task_name": "notion-digest-scout",
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
    }
  ],
  "created_at": "${NOW}",
  "updated_at": "${NOW}",
  "started_at": null,
  "completed_at": null,
  "error": null
}
EOJSON

echo "📋 週次scoutタスクファイルを作成しました"
echo "   タスクID: ${TASK_ID}"
echo "   タスク名: scout_weekly"
echo "   基準日:   ${BASE_DATE}"
echo "   子タスク: 9件"
echo "   ファイル: ${FILEPATH}"

# RSS事前取得（イベント系）
echo "📡 RSSフィード事前取得中..."
python3.12 ~/scripts/fetch-rss-feeds.py --category tech_events --date "${BASE_DATE}" --no-filter 2>/dev/null && echo "   ✅ tech_events フィード取得完了" || echo "   ⚠️ tech_events フィード取得失敗（続行）"
python3.12 ~/scripts/fetch-rss-feeds.py --category lifestyle_events --date "${BASE_DATE}" --no-filter 2>/dev/null && echo "   ✅ lifestyle_events フィード取得完了" || echo "   ⚠️ lifestyle_events フィード取得失敗（続行）"
