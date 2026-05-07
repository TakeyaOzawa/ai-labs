#!/bin/zsh
set -eu -o pipefail

# run-weekly-pipeline: 週次scoutパイプラインをkiro-cliで実行する
#
# 目的:
#   週次scoutパイプラインの全エージェントを順次実行し、
#   digest集約→イベント収集→ブログ素材→ブログ企画を一括で行う。
#
# 使い方:
#   run-weekly-pipeline.sh [基準日]
#
# 例:
#   run-weekly-pipeline.sh 2026-05-07
#
# 出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
# 依存: kiro-cli, caffeinate

BASE_DATE="${1:-$(TZ=Asia/Tokyo date +%Y-%m-%d)}"
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

# ─── ログローテーション（1000行超で切り詰め） ────────────────────
LOG_FILE="$LOG_DIR/scout-weekly-pipeline.log"
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 1000 ]; then
  tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

echo "[$NOW] 📋 週次scoutパイプライン起動（基準日: $BASE_DATE）"

# ─── Step 1: 週次エージェントを順次実行 ──────────────────────────
echo "[$NOW] Step 1: 週次scoutエージェント実行開始..."

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
  "tech-blog-planner"
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

  # 週次パイプラインモード対象かどうかでプロンプトを分岐
  case "$AGENT" in
    tech-event-scout|lifestyle-event-scout|tech-blog-material-scout|tech-blog-planner)
      PROMPT="${AGENT} エージェントとして「週次パイプラインモード」で動作してください。"
      PROMPT="${PROMPT} ~/.kiro/agents/prompts/${AGENT}.md をreadFileで読み込み、"
      PROMPT="${PROMPT}そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
      PROMPT="${PROMPT}基準日は ${BASE_DATE} です。"
      PROMPT="${PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
      ;;
    *)
      PROMPT="${AGENT} エージェントとして動作してください。"
      PROMPT="${PROMPT} ~/.kiro/agents/prompts/${AGENT}.md をreadFileで読み込み、"
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
  else
    AGENT_END=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
    echo "[$AGENT_END]    ❌ $AGENT 失敗（ログ: $AGENT_LOG）"
    FAILED=$((FAILED + 1))
    FAILED_NAMES="${FAILED_NAMES} ${AGENT}"
  fi
done

# ─── Step 2: 完了サマリー ────────────────────────────────────────
END_NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
TOTAL=$((SUCCESS + FAILED))
echo "[$END_NOW] 📊 実行完了: ✅${SUCCESS}件 / ❌${FAILED}件 (全${TOTAL}件)"
if [ $FAILED -gt 0 ]; then
  echo "[$END_NOW]    失敗:${FAILED_NAMES}"
fi

echo "[$END_NOW] ✅ 週次scoutパイプライン完了（基準日: $BASE_DATE）"
