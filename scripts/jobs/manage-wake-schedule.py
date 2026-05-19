#!/usr/bin/env python3.12
"""
manage-wake-schedule: macOSのスケジュール起床（pmset repeat）を管理する

目的:
    launchdで深夜にスケジュールされたジョブ（run-daily-pipeline 2:30、
    run-weekly-pipeline 土曜3:30）は、Macがスリープ中だと発火しない。
    pmset repeat でスリープからの自動起床を設定することで、
    深夜のジョブが確実に実行されるようにする。
    ※ 電源接続時のみ確実に動作。バッテリー駆動時は起床しない場合がある。
    ※ Linux環境では非サポート（サーバーはスリープしない前提）。

使い方:
    python3.12 scripts/manage-wake-schedule.py status
    python3.12 scripts/manage-wake-schedule.py set HH:MM [--days MTWRFSU]
    python3.12 scripts/manage-wake-schedule.py unset

出力: JSON形式
注意: set/unsetにはsudo権限が必要
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import json
import subprocess

# ─── 定数 ────────────────────────────────────────────────────────

PLATFORM_CMD = Path(__file__).parent / "platform-commands.sh"


# ─── メイン ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "Usage: manage-wake-schedule.py <status|set|unset> [options]",
            "examples": [
                "manage-wake-schedule.py status",
                "manage-wake-schedule.py set 02:25",
                "manage-wake-schedule.py set 02:25 --days MTWRF",
                "manage-wake-schedule.py unset",
            ],
        }))
        sys.exit(1)

    action = sys.argv[1]

    if action == "status":
        run_platform_command("pmset-status")

    elif action == "set":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "error": "Time argument required (HH:MM)"}))
            sys.exit(1)

        time_str = sys.argv[2]
        days = "MTWRFSU"

        # --days オプション解析
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--days" and i + 1 < len(sys.argv):
                days = sys.argv[i + 1]
                i += 2
            else:
                print(json.dumps({"success": False, "error": f"Unknown option: {sys.argv[i]}"}))
                sys.exit(1)

        run_platform_command("pmset-set", time_str, days)

    elif action == "unset":
        run_platform_command("pmset-unset")

    else:
        print(json.dumps({"success": False, "error": f"Unknown action: {action}"}))
        sys.exit(1)


def run_platform_command(command: str, *args: str) -> None:
    """platform-commands.sh を実行して結果を出力する。"""
    cmd = [str(PLATFORM_CMD), command, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        print(json.dumps({"success": False, "error": error_msg}))
        sys.exit(1)

    output = result.stdout.strip()
    if output:
        print(output)




if __name__ == "__main__":
    main()
