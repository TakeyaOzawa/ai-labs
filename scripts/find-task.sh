#!/bin/zsh
set -eu -o pipefail

# find-task: タスクファイルからタスクを検索しJSON形式で出力する
#
# 目的:
#   scoutパイプラインのタスク管理において、タスクの状態確認や
#   特定タスクの検索を行うための抽象レイヤー。
#   将来的にバックエンドをDB/APIに差し替え可能。
#
# 使い方:
#   find-task.sh --pipeline daily|weekly [--date YYYY-MM-DD] [--status STATUS] [--task-id ID] [--task-name NAME] [--scope parent|child] [--limit N]
#
# 例:
#   find-task.sh --pipeline daily --date 2026-05-07
#   find-task.sh --pipeline weekly --status running --limit 5
#
# オプション:
#   --pipeline   必須。daily または weekly
#   --date       基準日（省略時: 最新のタスクファイルを使用）
#   --status     フィルタするステータス（starting, running, pending, completed, failed）
#   --task-id    特定のtask_idで検索
#   --task-name  特定のtask_nameで検索
#   --scope      parent: 親タスクのみ返す / child: 子タスクのみ返す（デフォルト: child）
#   --limit      返す件数の上限（デフォルト: 1）
#
# 出力: JSON形式
# 依存: jq

PIPELINE=""
DATE=""
STATUS=""
TASK_ID=""
TASK_NAME=""
SCOPE="child"
LIMIT=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pipeline) PIPELINE="$2"; shift 2 ;;
    --date) DATE="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --task-id) TASK_ID="$2"; shift 2 ;;
    --task-name) TASK_NAME="$2"; shift 2 ;;
    --scope) SCOPE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PIPELINE" ]]; then
  echo '{"found": false, "error": "--pipeline is required (daily|weekly)"}' 
  exit 1
fi

# ディレクトリ決定
BASE_DIR="$HOME/Documents/works/agent_histories"
case "$PIPELINE" in
  daily)  DIR="$BASE_DIR/scout_daily" ;;
  weekly) DIR="$BASE_DIR/scout_weekly" ;;
  *)
    echo "{\"found\": false, \"error\": \"Invalid pipeline: $PIPELINE\"}"
    exit 1
    ;;
esac

# タスクファイル特定
if [[ -n "$DATE" ]]; then
  TASK_FILE=$(ls "$DIR"/${DATE}_*.json 2>/dev/null | head -1)
else
  TASK_FILE=$(ls -t "$DIR"/*.json 2>/dev/null | head -1)
fi

if [[ -z "$TASK_FILE" || ! -f "$TASK_FILE" ]]; then
  echo '{"found": false, "error": "No task file found", "task_file": null, "tasks": [], "parent": null}'
  exit 0
fi

# 親タスク情報を抽出
PARENT=$(jq '{task_id, task_name, status, status_detail, args, started_at, updated_at, completed_at, error}' "$TASK_FILE")

# scope=parent の場合は親タスクのみ返す
if [[ "$SCOPE" == "parent" ]]; then
  jq -n \
    --arg task_file "$TASK_FILE" \
    --argjson parent "$PARENT" \
    '{found: true, task_file: $task_file, tasks: [$parent], parent: $parent}'
  exit 0
fi

# 子タスクのフィルタリング
FILTER=".child_tasks"

if [[ -n "$STATUS" ]]; then
  FILTER="$FILTER | map(select(.status == \"$STATUS\"))"
fi

if [[ -n "$TASK_ID" ]]; then
  FILTER="$FILTER | map(select(.task_id == \"$TASK_ID\"))"
fi

if [[ -n "$TASK_NAME" ]]; then
  FILTER="$FILTER | map(select(.task_name == \"$TASK_NAME\"))"
fi

FILTER="$FILTER | .[:$LIMIT]"

TASKS=$(jq "$FILTER" "$TASK_FILE")
FOUND=$(echo "$TASKS" | jq 'length > 0')

jq -n \
  --argjson found "$FOUND" \
  --arg task_file "$TASK_FILE" \
  --argjson tasks "$TASKS" \
  --argjson parent "$PARENT" \
  '{found: $found, task_file: $task_file, tasks: $tasks, parent: $parent}'
