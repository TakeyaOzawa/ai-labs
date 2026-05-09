#!/bin/zsh
set -eu -o pipefail

# run-daily-pipeline: 日次scoutパイプラインをkiro-cliで実行する（タスク管理付き）
#
# 目的:
#   日次scoutパイプラインの全エージェントを順次実行し、
#   RSSフィード取得→各scout実行→結果サマリー出力を一括で行う。
#   Watcher方式と同等のタスクファイルベース進捗管理を行う。
#
# 使い方:
#   run-daily-pipeline.sh [基準日]
#
# 例:
#   run-daily-pipeline.sh 2026-05-07
#
# オプション:
#   --no-task-file   タスクファイルによる進捗管理を無効化（従来互換モード）
#
# 出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
# 依存: kiro-cli, python3.12 (fetch-rss-feeds.py), caffeinate, jq

# ─── オプション解析 ──────────────────────────────────────────────
USE_TASK_FILE=true
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-task-file) USE_TASK_FILE=false; shift ;;
    *) POSITIONAL_ARGS+=("$1"); shift ;;
  esac
done

BASE_DATE="${POSITIONAL_ARGS[1]:-$(TZ=Asia/Tokyo date -v-1d +%Y-%m-%d)}"
NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
LOG_DIR="$HOME/logs"

# スクリプト実行中はシステムのアイドルスリープを防止
caffeinate -i -w $$ &

mkdir -p "$LOG_DIR"

# ─── 環境変数の確認（MCP用トークン） ─────────────────────────────
# kiro-cliはmcp.jsonの${...}をプロセス環境変数から解決する
# .zshrcで定義された変数名がそのまま使われるため、sourceのみで十分
if [[ -z "${MY_SLACK_OAUTH_TOKEN:-}" ]]; then
  [[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc" 2>/dev/null || true
fi

# MCPサーバー（@modelcontextprotocol/server-slack）が直接参照する環境変数
# 収集フェーズ（slack-trend-scout）は slack-reference-home を使用
export SLACK_BOT_TOKEN="${SLACK_REFERENCE_BOT_TOKEN:-}"
export SLACK_TEAM_ID="${SLACK_REFERENCE_TEAM_ID:-}"

# ─── ログローテーション（1000行超で切り詰め） ────────────────────
LOG_FILE="$LOG_DIR/scout-daily-pipeline.log"
if [[ -f "$LOG_FILE" ]] && (( $(wc -l < "$LOG_FILE") > 1000 )); then
  tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

echo "[$NOW] 📋 日次scoutパイプライン起動（基準日: $BASE_DATE）"

# ─── Step 0: タスクファイル生成（進捗管理モード） ────────────────
TASK_FILE=""
if [[ "$USE_TASK_FILE" == "true" ]]; then
  echo "[$NOW] Step 0: タスクファイル生成..."
  TASK_OUTPUT=$("$HOME/scripts/create-daily-tasks.sh" "$BASE_DATE" 2>&1) || true
  echo "$TASK_OUTPUT"
  # create-daily-tasks.shの出力からファイルパスを抽出
  TASK_FILE=$(echo "$TASK_OUTPUT" | grep "ファイル:" | sed 's/.*ファイル: //')
  if [[ -z "$TASK_FILE" || ! -f "$TASK_FILE" ]]; then
    echo "[$NOW] ⚠️  タスクファイル生成失敗。進捗管理なしで続行。"
    USE_TASK_FILE=false
  else
    echo "[$NOW]    タスクファイル: $TASK_FILE"
    # 親タスクをrunningに更新
    "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --scope parent \
      --set "{\"status\": \"running\", \"started_at\": \"$NOW\"}" >/dev/null || true
  fi
fi

# ─── Step 1: RSSフィード事前取得 ─────────────────────────────────
echo "[$NOW] Step 1: RSSフィード事前取得..."
RSS_SCRIPT="$HOME/scripts/fetch-rss-feeds.py"
if [[ -f "$RSS_SCRIPT" ]]; then
  python3.12 "$RSS_SCRIPT" --category tech --date "$BASE_DATE" 2>/dev/null && echo "   ✅ tech" || echo "   ⚠️  tech (失敗・続行)"
  python3.12 "$RSS_SCRIPT" --category biz --date "$BASE_DATE" 2>/dev/null && echo "   ✅ biz" || echo "   ⚠️  biz (失敗・続行)"
  python3.12 "$RSS_SCRIPT" --category academic --date "$BASE_DATE" 2>/dev/null && echo "   ✅ academic" || echo "   ⚠️  academic (失敗・続行)"
else
  echo "   ⚠️  RSSスクリプト未検出（スキップ）"
fi

# ─── Step 2: 各scoutエージェントを順次実行 ───────────────────────
echo "[$NOW] Step 2: scoutエージェント実行開始..."

AGENTS=(
  "tech-trend-scout"
  "biz-car-trend-scout"
  "academic-trend-scout"
  "gws-trend-scout"
  "slack-trend-scout"
  "github-org-trend-scout"
  "github-public-trend-scout"
  "notion-trend-scout"
)

SUCCESS=0
FAILED=0
FAILED_NAMES=""

for AGENT in "${AGENTS[@]}"; do
  AGENT_START=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
  echo "[$AGENT_START] 🔄 $AGENT 実行中..."

  AGENT_LOG="$LOG_DIR/scout-daily-${AGENT}.log"

  # エージェント別ログもローテーション
  if [[ -f "$AGENT_LOG" ]] && (( $(wc -l < "$AGENT_LOG") > 500 )); then
    tail -100 "$AGENT_LOG" > "$AGENT_LOG.tmp" && mv "$AGENT_LOG.tmp" "$AGENT_LOG"
  fi

  # ─── タスクファイル: running に更新 ─────────────────────────
  CHILD_TASK_ID=""
  if [[ "$USE_TASK_FILE" == "true" ]]; then
    # タスクファイルから該当タスクのIDを取得
    CHILD_TASK_ID=$(jq -r --arg name "$AGENT" '.child_tasks[] | select(.task_name == $name) | .task_id' "$TASK_FILE")
    if [[ -n "$CHILD_TASK_ID" ]]; then
      "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --task-id "$CHILD_TASK_ID" \
        --set "{\"status\": \"running\", \"started_at\": \"$AGENT_START\"}" >/dev/null || true
      "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --scope parent \
        --set "{\"status_detail\": \"$AGENT 実行中\"}" >/dev/null || true
    fi
  fi

  # ─── エージェント実行 ───────────────────────────────────────
  # プロンプトを変数に格納（バッククォート問題を回避）
  PROMPT="${AGENT} エージェントとして動作してください。"
  PROMPT="${PROMPT} ~/.shared-ai/prompts/${AGENT}.md をreadFileで読み込み、"
  PROMPT="${PROMPT}そこに記載されたワークフローに従って実行してください。"
  PROMPT="${PROMPT}基準日は ${BASE_DATE} です。"
  PROMPT="${PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"

  if kiro-cli chat --trust-all-tools --no-interactive \
    "$PROMPT" \
    >> "$AGENT_LOG" 2>&1; then
    AGENT_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
    echo "[$AGENT_END]    ✅ $AGENT 完了"
    SUCCESS=$((SUCCESS + 1))

    # ─── タスクファイル: completed に更新 ───────────────────
    if [[ "$USE_TASK_FILE" == "true" && -n "$CHILD_TASK_ID" ]]; then
      "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --task-id "$CHILD_TASK_ID" \
        --set "{\"status\": \"completed\", \"completed_at\": \"$AGENT_END\"}" >/dev/null || true
    fi
  else
    AGENT_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
    echo "[$AGENT_END]    ❌ $AGENT 失敗（ログ: $AGENT_LOG）"
    FAILED=$((FAILED + 1))
    FAILED_NAMES="${FAILED_NAMES} ${AGENT}"

    # ─── タスクファイル: failed に更新 ─────────────────────
    if [[ "$USE_TASK_FILE" == "true" && -n "$CHILD_TASK_ID" ]]; then
      "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --task-id "$CHILD_TASK_ID" \
        --set "{\"status\": \"failed\", \"error\": \"kiro-cli exit non-zero\", \"completed_at\": \"$AGENT_END\"}" >/dev/null || true
    fi
  fi
done

# ─── Step 3: 親タスク完了処理 ────────────────────────────────────
END_NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
TOTAL=$((SUCCESS + FAILED))

if [[ "$USE_TASK_FILE" == "true" ]]; then
  if (( FAILED > 0 )); then
    "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --scope parent \
      --set "{\"status\": \"failed\", \"completed_at\": \"$END_NOW\", \"status_detail\": \"${FAILED}件失敗:${FAILED_NAMES}\", \"error\": \"${FAILED}/${TOTAL} tasks failed\"}" >/dev/null || true
  else
    "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --scope parent \
      --set "{\"status\": \"completed\", \"completed_at\": \"$END_NOW\", \"status_detail\": \"全子タスク完了\"}" >/dev/null || true
  fi
fi

# ─── Step 4: Slack通知（全scout完了後に一括実行） ────────────────
NOTIFY_NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
echo "[$NOTIFY_NOW] Step 4: Slack通知..."

# 通知用MCPサーバー（slack-notification-home）は MY_SLACK_OAUTH_TOKEN を使用
# 収集フェーズで参照用にセットした SLACK_BOT_TOKEN を通知用に切り替える
export SLACK_BOT_TOKEN="${MY_SLACK_OAUTH_TOKEN:-}"

# エージェント名 → 出力ファイルパスのマッピング
typeset -A NOTIFY_FILES
NOTIFY_FILES[tech-trend-scout]="$HOME/Documents/works/scout_histories/tech_trends/daily/${BASE_DATE}_tech_trends.md"
NOTIFY_FILES[biz-car-trend-scout]="$HOME/Documents/works/scout_histories/biz_car_trends/daily/${BASE_DATE}_biz_car_trends.md"
NOTIFY_FILES[academic-trend-scout]="$HOME/Documents/works/scout_histories/academic_trends/daily/${BASE_DATE}_academic_trends.md"
NOTIFY_FILES[gws-trend-scout]="$HOME/Documents/works/scout_histories/gws_trends/daily/${BASE_DATE}_gws_daily.md"
NOTIFY_FILES[slack-trend-scout]="$HOME/Documents/works/scout_histories/slack_trends/daily/${BASE_DATE}_slack_daily.md"
NOTIFY_FILES[github-org-trend-scout]="$HOME/Documents/works/scout_histories/github_org_trends/daily/${BASE_DATE}_github-org_daily.md"
NOTIFY_FILES[github-public-trend-scout]="$HOME/Documents/works/scout_histories/github_public_trends/daily/${BASE_DATE}_github-public_daily.md"
NOTIFY_FILES[notion-trend-scout]="$HOME/Documents/works/scout_histories/notion_trends/daily/${BASE_DATE}_notion_daily.md"

NOTIFY_SUCCESS=0
NOTIFY_SKIPPED=0

for AGENT in "${AGENTS[@]}"; do
  FILE_PATH="${NOTIFY_FILES[$AGENT]:-}"
  if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
    echo "   ⏭️  $AGENT: 出力ファイルなし（スキップ）"
    NOTIFY_SKIPPED=$((NOTIFY_SKIPPED + 1))
    continue
  fi

  NOTIFY_START=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
  echo "[$NOTIFY_START]    📨 $AGENT 通知中..."

  NOTIFY_PROMPT="slack-notifier エージェントとして動作してください。"
  NOTIFY_PROMPT="${NOTIFY_PROMPT} ~/.shared-ai/prompts/slack-notifier.md をreadFileで読み込み、"
  NOTIFY_PROMPT="${NOTIFY_PROMPT}そこに記載されたワークフローに従って実行してください。"
  NOTIFY_PROMPT="${NOTIFY_PROMPT} file_path=${FILE_PATH}"

  if kiro-cli chat --trust-all-tools --no-interactive \
    "$NOTIFY_PROMPT" \
    >> "$LOG_DIR/scout-daily-slack-notify.log" 2>&1; then
    echo "[$NOTIFY_START]    ✅ $AGENT 通知完了"
    NOTIFY_SUCCESS=$((NOTIFY_SUCCESS + 1))
  else
    echo "[$NOTIFY_START]    ⚠️  $AGENT 通知失敗（レポート作成は成功扱い）"
  fi
done

NOTIFY_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
echo "[$NOTIFY_END] 📨 通知完了: ✅${NOTIFY_SUCCESS}件 / ⏭️${NOTIFY_SKIPPED}件スキップ"

# ─── Step 5: 完了サマリー ────────────────────────────────────────
echo "[$NOTIFY_END] 📊 実行完了: ✅${SUCCESS}件 / ❌${FAILED}件 (全${TOTAL}件)"
if (( FAILED > 0 )); then
  echo "[$NOTIFY_END]    失敗:${FAILED_NAMES}"
fi

if [[ "$USE_TASK_FILE" == "true" ]]; then
  echo "[$NOTIFY_END]    タスクファイル: $TASK_FILE"
fi

echo "[$NOTIFY_END] ✅ 日次scoutパイプライン完了（基準日: $BASE_DATE）"
