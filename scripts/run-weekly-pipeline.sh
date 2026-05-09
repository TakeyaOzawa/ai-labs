#!/bin/zsh
set -eu -o pipefail

# run-weekly-pipeline: 週次scoutパイプラインをkiro-cliで実行する（タスク管理付き）
#
# 目的:
#   週次scoutパイプラインの全エージェントを順次実行し、
#   digest集約→イベント収集→ブログ素材→ブログ企画を一括で行う。
#   Watcher方式と同等のタスクファイルベース進捗管理を行う。
#
# 使い方:
#   run-weekly-pipeline.sh [基準日]
#
# 例:
#   run-weekly-pipeline.sh 2026-05-07
#
# オプション:
#   --no-task-file   タスクファイルによる進捗管理を無効化（従来互換モード）
#
# 出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
# 依存: kiro-cli, caffeinate, jq

# ─── オプション解析 ──────────────────────────────────────────────
USE_TASK_FILE=true
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-task-file) USE_TASK_FILE=false; shift ;;
    *) POSITIONAL_ARGS+=("$1"); shift ;;
  esac
done

BASE_DATE="${POSITIONAL_ARGS[1]:-$(TZ=Asia/Tokyo date +%Y-%m-%d)}"
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
export SLACK_BOT_TOKEN="${SLACK_REFERENCE_BOT_TOKEN:-}"
export SLACK_TEAM_ID="${SLACK_REFERENCE_TEAM_ID:-}"

# ─── ログローテーション（1000行超で切り詰め） ────────────────────
LOG_FILE="$LOG_DIR/scout-weekly-pipeline.log"
if [[ -f "$LOG_FILE" ]] && (( $(wc -l < "$LOG_FILE") > 1000 )); then
  tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

echo "[$NOW] 📋 週次scoutパイプライン起動（基準日: $BASE_DATE）"

# ─── Step 0: タスクファイル生成（進捗管理モード） ────────────────
TASK_FILE=""
if [[ "$USE_TASK_FILE" == "true" ]]; then
  echo "[$NOW] Step 0: タスクファイル生成..."
  TASK_OUTPUT=$("$HOME/scripts/create-weekly-tasks.sh" "$BASE_DATE" 2>&1) || true
  echo "$TASK_OUTPUT"
  # create-weekly-tasks.shの出力からファイルパスを抽出
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

# ─── Step 1: RSSフィード事前取得（イベント系） ───────────────────
echo "[$NOW] Step 1: RSSフィード事前取得..."
RSS_SCRIPT="$HOME/scripts/fetch-rss-feeds.py"
if [[ -f "$RSS_SCRIPT" ]]; then
  python3.12 "$RSS_SCRIPT" --category tech_events --date "$BASE_DATE" --no-filter 2>/dev/null && echo "   ✅ tech_events" || echo "   ⚠️  tech_events (失敗・続行)"
  python3.12 "$RSS_SCRIPT" --category lifestyle_events --date "$BASE_DATE" --no-filter 2>/dev/null && echo "   ✅ lifestyle_events" || echo "   ⚠️  lifestyle_events (失敗・続行)"
else
  echo "   ⚠️  RSSスクリプト未検出（スキップ）"
fi

# ─── Step 2: 週次エージェントを順次実行 ──────────────────────────
echo "[$NOW] Step 2: 週次scoutエージェント実行開始..."

# 実行するエージェント一覧
# digest系（日次レポート集約）→ イベント系 → ブログ素材 → ブログ企画
AGENTS=(
  "slack-digest-scout"
  "gws-digest-scout"
  "notion-digest-scout"
  "github-org-digest-scout"
  "github-public-digest-scout"
  "tech-event-scout"
  "lifestyle-event-scout"
  "tech-blog-material-scout"
  "tech-poc-planner"
)

SUCCESS=0
FAILED=0
FAILED_NAMES=""

for AGENT in "${AGENTS[@]}"; do
  AGENT_START=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
  echo "[$AGENT_START] 🔄 $AGENT 実行中..."

  AGENT_LOG="$LOG_DIR/scout-weekly-${AGENT}.log"

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
  # 週次パイプラインモード対象かどうかでプロンプトを分岐
  case "$AGENT" in
    tech-event-scout|lifestyle-event-scout|tech-blog-material-scout)
      PROMPT="${AGENT} エージェントとして「週次パイプラインモード」で動作してください。"
      PROMPT="${PROMPT} ~/.shared-ai/prompts/${AGENT}.md をreadFileで読み込み、"
      PROMPT="${PROMPT}そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
      PROMPT="${PROMPT}基準日は ${BASE_DATE} です。"
      PROMPT="${PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
      ;;
    tech-poc-planner)
      # tech-poc-plannerは素材シート1件ごとに個別起動する（コンテキスト節約）
      # ここではスキップし、後続のStep 2.5で処理する
      echo "[$AGENT_START]    ⏭️  $AGENT: Step 2.5で個別実行（スキップ）"
      SUCCESS=$((SUCCESS + 1))
      if [[ "$USE_TASK_FILE" == "true" && -n "$CHILD_TASK_ID" ]]; then
        "$HOME/scripts/update-task.sh" --task-file "$TASK_FILE" --task-id "$CHILD_TASK_ID" \
          --set "{\"status\": \"completed\", \"completed_at\": \"$AGENT_START\", \"status_detail\": \"Step 2.5で個別実行\"}" >/dev/null || true
      fi
      continue
      ;;
    *)
      PROMPT="${AGENT} エージェントとして動作してください。"
      PROMPT="${PROMPT} ~/.shared-ai/prompts/${AGENT}.md をreadFileで読み込み、"
      PROMPT="${PROMPT}そこに記載されたワークフローに従って実行してください。"
      PROMPT="${PROMPT}基準日は ${BASE_DATE} です。"
      PROMPT="${PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
      ;;
  esac

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

# ─── Step 2.5: tech-poc-planner 個別実行（素材シート1件ごと） ──
PLANNER_NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
echo "[$PLANNER_NOW] Step 2.5: tech-poc-planner 個別実行..."

MATERIAL_DIR="$HOME/Documents/works/scout_histories/tech_blog_materials/weekly"
PLANNER_LOG="$LOG_DIR/scout-weekly-tech-poc-planner.log"
PLANNER_SUCCESS=0
PLANNER_FAILED=0

# ログローテーション
if [[ -f "$PLANNER_LOG" ]] && (( $(wc -l < "$PLANNER_LOG") > 500 )); then
  tail -100 "$PLANNER_LOG" > "$PLANNER_LOG.tmp" && mv "$PLANNER_LOG.tmp" "$PLANNER_LOG"
fi

# 当該基準日の素材シートを列挙
MATERIAL_FILES=()
for f in "$MATERIAL_DIR/${BASE_DATE}_"*_material.md(N); do
  [[ -f "$f" ]] && MATERIAL_FILES+=("$f")
done

if (( ${#MATERIAL_FILES[@]} == 0 )); then
  echo "[$PLANNER_NOW]    ⚠️  素材シートなし（${BASE_DATE}_*_material.md）"
else
  echo "[$PLANNER_NOW]    📄 素材シート ${#MATERIAL_FILES[@]} 件検出"

  for MATERIAL_FILE in "${MATERIAL_FILES[@]}"; do
    MATERIAL_NAME=$(basename "$MATERIAL_FILE")
    PLAN_START=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
    echo "[$PLAN_START]    🔄 tech-poc-planner: $MATERIAL_NAME"

    PLANNER_PROMPT="tech-poc-planner エージェントとして「週次パイプラインモード」で動作してください。"
    PLANNER_PROMPT="${PLANNER_PROMPT} ~/.shared-ai/prompts/tech-poc-planner.md をreadFileで読み込み、"
    PLANNER_PROMPT="${PLANNER_PROMPT}そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
    PLANNER_PROMPT="${PLANNER_PROMPT} 素材シート: ${MATERIAL_FILE}"
    PLANNER_PROMPT="${PLANNER_PROMPT} 基準日は ${BASE_DATE} です。"
    PLANNER_PROMPT="${PLANNER_PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"

    if kiro-cli chat --trust-all-tools --no-interactive \
      "$PLANNER_PROMPT" \
      >> "$PLANNER_LOG" 2>&1; then
      PLAN_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
      echo "[$PLAN_END]       ✅ $MATERIAL_NAME 完了"
      PLANNER_SUCCESS=$((PLANNER_SUCCESS + 1))
    else
      PLAN_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
      echo "[$PLAN_END]       ❌ $MATERIAL_NAME 失敗"
      PLANNER_FAILED=$((PLANNER_FAILED + 1))
    fi
  done

  PLANNER_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
  echo "[$PLANNER_END]    📊 tech-poc-planner: ✅${PLANNER_SUCCESS}件 / ❌${PLANNER_FAILED}件"
fi

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
NOTIFY_FILES[slack-digest-scout]="$HOME/Documents/works/scout_histories/slack_trends/weekly/${BASE_DATE}_slack_weekly_digest.md"
NOTIFY_FILES[gws-digest-scout]="$HOME/Documents/works/scout_histories/gws_trends/weekly/${BASE_DATE}_gws_weekly_digest.md"
NOTIFY_FILES[notion-digest-scout]="$HOME/Documents/works/scout_histories/notion_trends/weekly/${BASE_DATE}_notion_weekly_digest.md"
NOTIFY_FILES[github-org-digest-scout]="$HOME/Documents/works/scout_histories/github_org_trends/weekly/${BASE_DATE}_github-org_weekly_digest.md"
NOTIFY_FILES[github-public-digest-scout]="$HOME/Documents/works/scout_histories/github_public_trends/weekly/${BASE_DATE}_github-public_weekly_digest.md"
NOTIFY_FILES[tech-event-scout]="$HOME/Documents/works/scout_histories/tech_events/weekly/${BASE_DATE}_tech_events.md"
NOTIFY_FILES[lifestyle-event-scout]="$HOME/Documents/works/scout_histories/lifestyle_events/weekly/${BASE_DATE}_lifestyle_events.md"

NOTIFY_SUCCESS=0
NOTIFY_SKIPPED=0

for AGENT in "${AGENTS[@]}"; do
  # tech-blog-material-scout / tech-poc-planner は複数ファイル出力のため通知スキップ
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
    >> "$LOG_DIR/scout-weekly-slack-notify.log" 2>&1; then
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

echo "[$NOTIFY_END] ✅ 週次scoutパイプライン完了（基準日: $BASE_DATE）"
