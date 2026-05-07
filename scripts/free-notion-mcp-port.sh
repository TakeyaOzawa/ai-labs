#!/bin/zsh
set -eu -o pipefail

# free-notion-mcp-port: Notion MCPサーバーのポート競合を解消する
#
# 目的:
#   Notion MCP（SSE接続）がEADDRINUSEエラーで起動失敗した際に、
#   ポート9553を占有しているプロセスを停止してポートを解放する。
#
# 使い方:
#   free-notion-mcp-port.sh
#
# 出力: 標準出力にメッセージ
# 注意: 対象プロセスをkillする破壊的操作

PORT=9553

PID=$(lsof -ti :$PORT)
if [ -n "$PID" ]; then
  echo "ポート${PORT}を使用中のプロセス(PID: $PID)を停止します..."
  kill $PID
  sleep 1
  # まだ残っていれば強制終了
  if lsof -ti :$PORT > /dev/null 2>&1; then
    echo "通常終了できなかったため強制終了します..."
    kill -9 $(lsof -ti :$PORT) 2>/dev/null
  fi
  echo "完了: ポート${PORT}が解放されました"
else
  echo "ポート${PORT}を使用中のプロセスはありません"
fi
