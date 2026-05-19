#!/usr/bin/env python3.12
"""
free-notion-mcp-port: Notion MCPサーバーのポート競合を解消する

目的:
    Notion MCP（SSE接続）がEADDRINUSEエラーで起動失敗した際に、
    ポート9553を占有しているプロセスを停止してポートを解放する。

使い方:
    python3.12 scripts/free-notion-mcp-port.py

出力: 標準出力にメッセージ
注意: 対象プロセスをkillする破壊的操作
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
import subprocess

# ─── 定数 ────────────────────────────────────────────────────────

PORT = 9553
PLATFORM_CMD = Path(__file__).parent / "platform-commands.sh"


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    result = subprocess.run(
        [str(PLATFORM_CMD), "kill-port", str(PORT)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"エラー: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        print(result.stdout.strip())
        return

    if data.get("pid"):
        print(f"完了: ポート{PORT}を使用中のプロセス(PID: {data['pid']})を停止しました")
    else:
        print(f"ポート{PORT}を使用中のプロセスはありません")




if __name__ == "__main__":
    main()
