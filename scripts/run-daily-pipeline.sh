#!/bin/zsh
set -eu -o pipefail

# run-daily-pipeline: 日次scoutパイプラインをkiro-cliで実行する
#
# 目的:
#   日次scoutパイプラインの全エージェントを順次実行し、
#   RSSフィード取得→各scout実行→結果サマリー出力を一括で行う。
#
# 使い方:
#   run-daily-pipeline.sh [基準日]
#
# 例:
#   run-daily-pipeline.sh 2026-05-07
#
# 出力: 各scoutエージェントの実行結果（標準出力 + ログファイル）
# 依存: kiro-cli, python3.12 (fetch-rss-feeds.py), caffeinate

BASE_DATE="${1:-$(TZ=Asia/Tokyo date -v-1d +%Y-%m-%d)}"
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
LOG_FILE="$LOG_DIR/scout-daily-pipeline.log"
if [[ -f "$LOG_FILE" ]] && (( $(wc -l < "$LOG_FILE") > 1000 )); then
  tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

echo "[$NOW] 📋 日次scoutパイプライン起動（基準日: $BASE_DATE）"

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

  # プロンプトを変数に格納（バッククォート問題を回避）
  PROMPT="${AGENT} エージェントとして動作してください。"
  PROMPT="${PROMPT} ~/.kiro/agents/prompts/${AGENT}.md をreadFileで読み込み、"
  PROMPT="${PROMPT}そこに記載されたワークフローに従って実行してください。"
  PROMPT="${PROMPT}基準日は ${BASE_DATE} です。"
  PROMPT="${PROMPT}日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"

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

# ─── Step 3: 完了サマリー ────────────────────────────────────────
END_NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
TOTAL=$((SUCCESS + FAILED))
echo "[$END_NOW] 📊 実行完了: ✅${SUCCESS}件 / ❌${FAILED}件 (全${TOTAL}件)"
if (( FAILED > 0 )); then
  echo "[$END_NOW]    失敗:${FAILED_NAMES}"
fi

echo "[$END_NOW] ✅ 日次scoutパイプライン完了（基準日: $BASE_DATE）"
