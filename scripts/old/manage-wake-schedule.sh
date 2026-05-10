#!/bin/zsh
set -eu -o pipefail

# manage-wake-schedule: macOSのスケジュール起床（pmset repeat）を管理する
#
# 目的:
#   launchdで深夜にスケジュールされたジョブ（run-daily-pipeline.sh 2:30、
#   run-weekly-pipeline.sh 土曜3:30）は、Macがスリープ中だと発火しない。
#   pmset repeat でスリープからの自動起床を設定することで、
#   深夜のジョブが確実に実行されるようにする。
#   ※ 電源接続時のみ確実に動作。バッテリー駆動時は起床しない場合がある。
#   ※ 設定しなくても、起床後にlaunchdが1回実行するため実害は少ない。
#
# 使い方:
#   manage-wake-schedule.sh status              — 現在の設定を表示
#   manage-wake-schedule.sh set HH:MM           — 毎日指定時刻に起床する設定を追加
#   manage-wake-schedule.sh set HH:MM --days MTWRFSU — 曜日指定で設定
#   manage-wake-schedule.sh unset               — スケジュール起床設定を削除
# 出力: JSON形式
# 注意: set/unsetにはsudo権限が必要

usage() {
  cat << 'EOF'
{"success": false, "error": "Usage: manage-wake-schedule.sh <status|set|unset> [options]", "examples": [
  "manage-wake-schedule.sh status",
  "manage-wake-schedule.sh set 02:25",
  "manage-wake-schedule.sh set 02:25 --days MTWRF",
  "manage-wake-schedule.sh unset"
]}
EOF
  exit 1
}

[ $# -lt 1 ] && usage

ACTION="$1"
shift

case "$ACTION" in
  status)
    SCHED=$(pmset -g sched 2>&1)
    if echo "$SCHED" | grep -q "Repeating"; then
      # スケジュールが設定されている
      REPEAT_LINE=$(echo "$SCHED" | grep -A1 "Repeating" | tail -1)
      echo "{\"success\": true, \"action\": \"status\", \"scheduled\": true, \"raw\": \"$(echo "$REPEAT_LINE" | sed 's/"/\\"/g')\"}"
    else
      echo "{\"success\": true, \"action\": \"status\", \"scheduled\": false, \"message\": \"No repeating wake schedule configured\"}"
    fi
    ;;

  set)
    [ $# -lt 1 ] && usage
    TIME="$1"
    shift

    # 時刻フォーマット検証（HH:MM）
    if ! echo "$TIME" | grep -qE '^[0-2][0-9]:[0-5][0-9]$'; then
      echo "{\"success\": false, \"error\": \"Invalid time format. Use HH:MM (e.g. 02:25)\"}"
      exit 1
    fi

    # 曜日オプション（デフォルト: 毎日）
    DAYS="MTWRFSU"
    while [ $# -gt 0 ]; do
      case "$1" in
        --days)
          shift
          DAYS="${1:-MTWRFSU}"
          shift
          ;;
        *)
          echo "{\"success\": false, \"error\": \"Unknown option: $1\"}"
          exit 1
          ;;
      esac
    done

    # pmset repeat設定（sudo必要）
    TIME_WITH_SECONDS="${TIME}:00"
    echo "sudo権限が必要です。パスワードを入力してください。" >&2
    if sudo pmset repeat wakeorpoweron "$DAYS" "$TIME_WITH_SECONDS" 2>&1; then
      echo "{\"success\": true, \"action\": \"set\", \"time\": \"$TIME\", \"days\": \"$DAYS\", \"message\": \"Wake schedule set: $DAYS at $TIME\"}"
    else
      echo "{\"success\": false, \"error\": \"Failed to set wake schedule. sudo permission required.\"}"
      exit 1
    fi
    ;;

  unset)
    echo "sudo権限が必要です。パスワードを入力してください。" >&2
    if sudo pmset repeat cancel 2>&1; then
      echo "{\"success\": true, \"action\": \"unset\", \"message\": \"Wake schedule removed\"}"
    else
      echo "{\"success\": false, \"error\": \"Failed to remove wake schedule. sudo permission required.\"}"
      exit 1
    fi
    ;;

  *)
    usage
    ;;
esac
