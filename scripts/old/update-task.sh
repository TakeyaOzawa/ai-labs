#!/bin/zsh
set -eu -o pipefail

# update-task: タスクファイル内の特定タスクのステータスを更新する
#
# 目的:
#   scoutパイプラインのタスク状態遷移を管理するための抽象レイヤー。
#   将来的にバックエンドをDB/APIに差し替え可能。
#
# 使い方:
#   update-task.sh --task-file /path/to/file.json --task-id ID --set '{"status": "running", ...}'
#   update-task.sh --task-file /path/to/file.json --scope parent --set '{"status": "running", ...}'
#
# 例:
#   update-task.sh --task-file ~/Documents/works/agent_histories/scout_daily/2026-05-07_xxx.json --task-id 01J... --set '{"status": "running"}'
#
# オプション:
#   --task-file  必須。対象タスクファイルのパス
#   --task-id    更新対象の子タスクID（--scope child 時に必須）
#   --scope      parent: 親タスクを更新 / child: 子タスクを更新（デフォルト: child）
#   --set        必須。更新するフィールドのJSON（例: '{"status": "running", "started_at": "...", "updated_at": "..."}'）
#
# --set で指定可能なフィールド:
#   status, status_detail, started_at, updated_at, completed_at, error
#
# 出力: JSON形式
# 依存: jq

TASK_FILE=""
TASK_ID=""
SCOPE="child"
SET_JSON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-file) TASK_FILE="$2"; shift 2 ;;
    --task-id) TASK_ID="$2"; shift 2 ;;
    --scope) SCOPE="$2"; shift 2 ;;
    --set) SET_JSON="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# バリデーション
if [[ -z "$TASK_FILE" ]]; then
  echo '{"success": false, "error": "--task-file is required"}'
  exit 1
fi

if [[ ! -f "$TASK_FILE" ]]; then
  echo "{\"success\": false, \"error\": \"Task file not found: $TASK_FILE\"}"
  exit 1
fi

if [[ -z "$SET_JSON" ]]; then
  echo '{"success": false, "error": "--set is required"}'
  exit 1
fi

# JSON妥当性チェック
if ! echo "$SET_JSON" | jq . >/dev/null 2>&1; then
  echo '{"success": false, "error": "Invalid JSON in --set"}'
  exit 1
fi

NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)

if [[ "$SCOPE" == "parent" ]]; then
  # 親タスクの更新
  BEFORE=$(jq '{status, status_detail, started_at, updated_at, completed_at, error}' "$TASK_FILE")
  
  # updated_at を自動付与（--set に含まれていなければ）
  HAS_UPDATED_AT=$(echo "$SET_JSON" | jq 'has("updated_at")')
  if [[ "$HAS_UPDATED_AT" == "false" ]]; then
    SET_JSON=$(echo "$SET_JSON" | jq --arg now "$NOW" '. + {updated_at: $now}')
  fi

  # jqで親タスクのフィールドを更新
  TEMP_FILE=$(mktemp)
  jq --argjson updates "$SET_JSON" '
    . as $root |
    reduce ($updates | to_entries[]) as $entry ($root;
      if $entry.key == "status" then .status = $entry.value
      elif $entry.key == "status_detail" then .status_detail = $entry.value
      elif $entry.key == "started_at" then .started_at = $entry.value
      elif $entry.key == "updated_at" then .updated_at = $entry.value
      elif $entry.key == "completed_at" then .completed_at = $entry.value
      elif $entry.key == "error" then .error = $entry.value
      else .
      end
    )
  ' "$TASK_FILE" > "$TEMP_FILE"
  mv "$TEMP_FILE" "$TASK_FILE"

  AFTER=$(jq '{status, status_detail, started_at, updated_at, completed_at, error}' "$TASK_FILE")
  OLD_STATUS=$(echo "$BEFORE" | jq -r '.status')
  NEW_STATUS=$(echo "$AFTER" | jq -r '.status')

  jq -n \
    --argjson before "$BEFORE" \
    --argjson after "$AFTER" \
    --arg task_file "$TASK_FILE" \
    --arg scope "parent" \
    --arg message "Parent updated: $OLD_STATUS → $NEW_STATUS" \
    '{success: true, task_file: $task_file, task_id: "parent", scope: $scope, before: $before, after: $after, message: $message}'

elif [[ "$SCOPE" == "child" ]]; then
  # 子タスクの更新
  if [[ -z "$TASK_ID" ]]; then
    echo '{"success": false, "error": "--task-id is required for child scope"}'
    exit 1
  fi

  # 対象子タスクが存在するか確認
  EXISTS=$(jq --arg id "$TASK_ID" '.child_tasks | map(select(.task_id == $id)) | length' "$TASK_FILE")
  if [[ "$EXISTS" == "0" ]]; then
    echo "{\"success\": false, \"error\": \"Child task not found: $TASK_ID\"}"
    exit 1
  fi

  BEFORE=$(jq --arg id "$TASK_ID" '.child_tasks[] | select(.task_id == $id) | {status, status_detail, started_at, updated_at, completed_at, error}' "$TASK_FILE")

  # updated_at を自動付与
  HAS_UPDATED_AT=$(echo "$SET_JSON" | jq 'has("updated_at")')
  if [[ "$HAS_UPDATED_AT" == "false" ]]; then
    SET_JSON=$(echo "$SET_JSON" | jq --arg now "$NOW" '. + {updated_at: $now}')
  fi

  # jqで子タスクのフィールドを更新
  TEMP_FILE=$(mktemp)
  jq --arg id "$TASK_ID" --argjson updates "$SET_JSON" '
    .child_tasks |= map(
      if .task_id == $id then
        reduce ($updates | to_entries[]) as $entry (.;
          if $entry.key == "status" then .status = $entry.value
          elif $entry.key == "status_detail" then .status_detail = $entry.value
          elif $entry.key == "started_at" then .started_at = $entry.value
          elif $entry.key == "updated_at" then .updated_at = $entry.value
          elif $entry.key == "completed_at" then .completed_at = $entry.value
          elif $entry.key == "error" then .error = $entry.value
          else .
          end
        )
      else .
      end
    )
  ' "$TASK_FILE" > "$TEMP_FILE"
  mv "$TEMP_FILE" "$TASK_FILE"

  AFTER=$(jq --arg id "$TASK_ID" '.child_tasks[] | select(.task_id == $id) | {status, status_detail, started_at, updated_at, completed_at, error}' "$TASK_FILE")
  OLD_STATUS=$(echo "$BEFORE" | jq -r '.status')
  NEW_STATUS=$(echo "$AFTER" | jq -r '.status')

  jq -n \
    --argjson before "$BEFORE" \
    --argjson after "$AFTER" \
    --arg task_file "$TASK_FILE" \
    --arg task_id "$TASK_ID" \
    --arg scope "child" \
    --arg message "Task $TASK_ID updated: $OLD_STATUS → $NEW_STATUS" \
    '{success: true, task_file: $task_file, task_id: $task_id, scope: $scope, before: $before, after: $after, message: $message}'
else
  echo "{\"success\": false, \"error\": \"Invalid scope: $SCOPE\"}"
  exit 1
fi
