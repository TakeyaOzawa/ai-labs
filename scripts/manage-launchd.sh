#!/bin/zsh
set -eu -o pipefail

# manage-launchd: LaunchAgentsジョブの管理（load/unload/status/reload）
#
# 目的:
#   scoutパイプラインのスケジュール実行を担うlaunchdジョブを
#   統一的なインターフェースで管理する。
#
# 使い方:
#   manage-launchd.sh <action> [label]
#
# 例:
#   manage-launchd.sh load scout-daily-pipeline
#   manage-launchd.sh unload scout-daily-pipeline
#   manage-launchd.sh reload scout-daily-pipeline
#   manage-launchd.sh status scout-daily-pipeline
#   manage-launchd.sh list
#
# 出力: JSON形式

AGENTS_DIR="$HOME/Library/LaunchAgents"
PREFIX="com.takeya"

usage() {
  echo '{"success": false, "error": "Usage: manage-launchd.sh <load|unload|reload|status|list> [label]"}'
  exit 1
}

[ $# -lt 1 ] && usage

ACTION="$1"
LABEL="${2:-}"

# labelからplistパスを解決
resolve_plist() {
  local label="$1"
  local plist="$AGENTS_DIR/${PREFIX}.${label}.plist"
  if [ ! -f "$plist" ]; then
    echo "{\"success\": false, \"error\": \"plist not found: $plist\"}"
    exit 1
  fi
  echo "$plist"
}

case "$ACTION" in
  load)
    [ -z "$LABEL" ] && usage
    PLIST=$(resolve_plist "$LABEL")
    launchctl load "$PLIST" 2>&1
    echo "{\"success\": true, \"action\": \"load\", \"label\": \"${PREFIX}.${LABEL}\", \"plist\": \"$PLIST\"}"
    ;;

  unload)
    [ -z "$LABEL" ] && usage
    PLIST=$(resolve_plist "$LABEL")
    launchctl unload "$PLIST" 2>&1
    echo "{\"success\": true, \"action\": \"unload\", \"label\": \"${PREFIX}.${LABEL}\", \"plist\": \"$PLIST\"}"
    ;;

  reload)
    [ -z "$LABEL" ] && usage
    PLIST=$(resolve_plist "$LABEL")
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST" 2>&1
    echo "{\"success\": true, \"action\": \"reload\", \"label\": \"${PREFIX}.${LABEL}\", \"plist\": \"$PLIST\"}"
    ;;

  status)
    [ -z "$LABEL" ] && usage
    FULL_LABEL="${PREFIX}.${LABEL}"
    RESULT=$(launchctl list | grep "$FULL_LABEL" || true)
    if [ -z "$RESULT" ]; then
      echo "{\"success\": true, \"label\": \"$FULL_LABEL\", \"loaded\": false}"
    else
      PID=$(echo "$RESULT" | awk '{print $1}')
      EXIT=$(echo "$RESULT" | awk '{print $2}')
      echo "{\"success\": true, \"label\": \"$FULL_LABEL\", \"loaded\": true, \"pid\": \"$PID\", \"last_exit_code\": \"$EXIT\"}"
    fi
    ;;

  list)
    JOBS=$(launchctl list | grep "$PREFIX" || true)
    if [ -z "$JOBS" ]; then
      echo "{\"success\": true, \"jobs\": []}"
    else
      echo "{\"success\": true, \"jobs\": ["
      FIRST=true
      echo "$JOBS" | while read -r line; do
        PID=$(echo "$line" | awk '{print $1}')
        EXIT=$(echo "$line" | awk '{print $2}')
        LBL=$(echo "$line" | awk '{print $3}')
        if [ "$FIRST" = true ]; then
          FIRST=false
        else
          echo ","
        fi
        echo "  {\"label\": \"$LBL\", \"pid\": \"$PID\", \"last_exit_code\": \"$EXIT\"}"
      done
      echo "]}"
    fi
    ;;

  *)
    usage
    ;;
esac
