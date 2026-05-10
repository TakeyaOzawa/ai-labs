#!/usr/bin/env python3.12
"""
manage-launchd: LaunchAgentsジョブの管理（load/unload/status/reload）

目的:
    scoutパイプラインのスケジュール実行を担うlaunchdジョブを
    統一的なインターフェースで管理する。
    Linux環境ではsystemctlにフォールバックする。

使い方:
    python3.12 scripts/manage-launchd.py <action> [label]

例:
    python3.12 scripts/manage-launchd.py load scout-daily-pipeline
    python3.12 scripts/manage-launchd.py unload scout-daily-pipeline
    python3.12 scripts/manage-launchd.py reload scout-daily-pipeline
    python3.12 scripts/manage-launchd.py status scout-daily-pipeline
    python3.12 scripts/manage-launchd.py list

出力: JSON形式
"""

import json
import subprocess
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

PLATFORM_CMD = Path(__file__).parent / "platform-commands.sh"


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "Usage: manage-launchd.py <load|unload|reload|status|list> [label]",
        }))
        sys.exit(1)

    action = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) >= 3 else ""

    valid_actions = {"load", "unload", "reload", "status", "list"}
    if action not in valid_actions:
        print(json.dumps({
            "success": False,
            "error": f"Unknown action: {action}. Valid: {', '.join(sorted(valid_actions))}",
        }))
        sys.exit(1)

    if action != "list" and not label:
        print(json.dumps({
            "success": False,
            "error": f"Label is required for action '{action}'",
        }))
        sys.exit(1)

    # platform-commands.sh に委譲
    cmd = [str(PLATFORM_CMD), "launchctl", action]
    if label:
        cmd.append(label)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        print(json.dumps({"success": False, "error": error_msg}))
        sys.exit(1)

    # platform-commands.sh はJSON出力するのでそのまま出力
    output = result.stdout.strip()
    if output:
        print(output)
    else:
        print(json.dumps({"success": True, "action": action, "label": label}))


if __name__ == "__main__":
    main()
