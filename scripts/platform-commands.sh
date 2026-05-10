#!/bin/bash
set -eu -o pipefail

# platform-commands: OS固有コマンドの抽象化レイヤー
#
# 目的:
#   macOSとLinuxで異なるコマンド体系を吸収し、Pythonスクリプトから
#   統一的に呼び出せるインターフェースを提供する。
#
# 使い方:
#   platform-commands.sh <command> [args...]
#
# コマンド一覧:
#   caffeinate-start <pid>       — スリープ防止開始（macOS: caffeinate, Linux: systemd-inhibit相当）
#   caffeinate-stop              — スリープ防止停止
#   launchctl <action> [label]   — サービス管理（macOS: launchctl, Linux: systemctl）
#   pmset-status                 — スケジュール起床の状態表示
#   pmset-set <time> [days]      — スケジュール起床の設定
#   pmset-unset                  — スケジュール起床の解除
#   lsof-port <port>             — ポート使用プロセスのPID取得
#   kill-port <port>             — ポート使用プロセスの停止
#   date-yesterday               — 昨日の日付（YYYY-MM-DD、JST）
#   source-env                   — 環境変数のロード（stdout にkey=value形式で出力）

OS="$(uname -s)"
COMMAND="${1:-}"
shift || true

case "$COMMAND" in

  # ─── caffeinate（スリープ防止） ──────────────────────────────────
  caffeinate-start)
    PID="${1:-$$}"
    if [[ "$OS" == "Darwin" ]]; then
      caffeinate -i -w "$PID" &
      echo "$!"
    else
      # Linux: systemd-inhibit がある場合はそれを使う
      # ない場合は何もしない（サーバー環境ではスリープしない前提）
      if command -v systemd-inhibit >/dev/null 2>&1; then
        systemd-inhibit --what=idle --who="scout-pipeline" --why="pipeline running" \
          tail --pid="$PID" -f /dev/null &
        echo "$!"
      else
        echo "0"
      fi
    fi
    ;;

  caffeinate-stop)
    CAFE_PID="${1:-}"
    if [[ -n "$CAFE_PID" && "$CAFE_PID" != "0" ]]; then
      kill "$CAFE_PID" 2>/dev/null || true
    fi
    ;;

  # ─── launchctl / systemctl ──────────────────────────────────────
  launchctl)
    ACTION="${1:-}"
    LABEL="${2:-}"
    PREFIX="com.takeya"
    AGENTS_DIR="$HOME/Library/LaunchAgents"

    if [[ "$OS" == "Darwin" ]]; then
      case "$ACTION" in
        load)
          PLIST="$AGENTS_DIR/${PREFIX}.${LABEL}.plist"
          [[ ! -f "$PLIST" ]] && echo "{\"success\": false, \"error\": \"plist not found: $PLIST\"}" && exit 1
          launchctl load "$PLIST" 2>&1
          echo "{\"success\": true, \"action\": \"load\", \"label\": \"${PREFIX}.${LABEL}\"}"
          ;;
        unload)
          PLIST="$AGENTS_DIR/${PREFIX}.${LABEL}.plist"
          [[ ! -f "$PLIST" ]] && echo "{\"success\": false, \"error\": \"plist not found: $PLIST\"}" && exit 1
          launchctl unload "$PLIST" 2>&1
          echo "{\"success\": true, \"action\": \"unload\", \"label\": \"${PREFIX}.${LABEL}\"}"
          ;;
        reload)
          PLIST="$AGENTS_DIR/${PREFIX}.${LABEL}.plist"
          [[ ! -f "$PLIST" ]] && echo "{\"success\": false, \"error\": \"plist not found: $PLIST\"}" && exit 1
          launchctl unload "$PLIST" 2>/dev/null || true
          launchctl load "$PLIST" 2>&1
          echo "{\"success\": true, \"action\": \"reload\", \"label\": \"${PREFIX}.${LABEL}\"}"
          ;;
        status)
          FULL_LABEL="${PREFIX}.${LABEL}"
          RESULT=$(launchctl list | grep "$FULL_LABEL" || true)
          if [[ -z "$RESULT" ]]; then
            echo "{\"success\": true, \"label\": \"$FULL_LABEL\", \"loaded\": false}"
          else
            PID=$(echo "$RESULT" | awk '{print $1}')
            EXIT=$(echo "$RESULT" | awk '{print $2}')
            echo "{\"success\": true, \"label\": \"$FULL_LABEL\", \"loaded\": true, \"pid\": \"$PID\", \"last_exit_code\": \"$EXIT\"}"
          fi
          ;;
        list)
          JOBS=$(launchctl list | grep "$PREFIX" || true)
          if [[ -z "$JOBS" ]]; then
            echo "{\"success\": true, \"jobs\": []}"
          else
            echo -n "{\"success\": true, \"jobs\": ["
            FIRST=true
            while IFS= read -r line; do
              PID=$(echo "$line" | awk '{print $1}')
              EXIT=$(echo "$line" | awk '{print $2}')
              LBL=$(echo "$line" | awk '{print $3}')
              if [[ "$FIRST" == "true" ]]; then
                FIRST=false
              else
                echo -n ","
              fi
              echo -n "{\"label\": \"$LBL\", \"pid\": \"$PID\", \"last_exit_code\": \"$EXIT\"}"
            done <<< "$JOBS"
            echo "]}"
          fi
          ;;
        *)
          echo "{\"success\": false, \"error\": \"Unknown launchctl action: $ACTION\"}"
          exit 1
          ;;
      esac
    else
      # Linux: systemctl で代替
      case "$ACTION" in
        load)
          systemctl --user start "${LABEL}.service" 2>&1
          echo "{\"success\": true, \"action\": \"load\", \"label\": \"${LABEL}\"}"
          ;;
        unload)
          systemctl --user stop "${LABEL}.service" 2>&1
          echo "{\"success\": true, \"action\": \"unload\", \"label\": \"${LABEL}\"}"
          ;;
        reload)
          systemctl --user restart "${LABEL}.service" 2>&1
          echo "{\"success\": true, \"action\": \"reload\", \"label\": \"${LABEL}\"}"
          ;;
        status)
          if systemctl --user is-active --quiet "${LABEL}.service" 2>/dev/null; then
            PID=$(systemctl --user show "${LABEL}.service" --property=MainPID --value)
            echo "{\"success\": true, \"label\": \"${LABEL}\", \"loaded\": true, \"pid\": \"$PID\", \"last_exit_code\": \"0\"}"
          else
            echo "{\"success\": true, \"label\": \"${LABEL}\", \"loaded\": false}"
          fi
          ;;
        list)
          echo "{\"success\": true, \"jobs\": []}"
          ;;
        *)
          echo "{\"success\": false, \"error\": \"Unknown action: $ACTION\"}"
          exit 1
          ;;
      esac
    fi
    ;;

  # ─── pmset（スケジュール起床） ──────────────────────────────────
  pmset-status)
    if [[ "$OS" == "Darwin" ]]; then
      SCHED=$(pmset -g sched 2>&1)
      if echo "$SCHED" | grep -q "Repeating"; then
        REPEAT_LINE=$(echo "$SCHED" | grep -A1 "Repeating" | tail -1)
        echo "{\"success\": true, \"scheduled\": true, \"raw\": \"$(echo "$REPEAT_LINE" | sed 's/"/\\"/g')\"}"
      else
        echo "{\"success\": true, \"scheduled\": false, \"message\": \"No repeating wake schedule configured\"}"
      fi
    else
      # Linux: rtcwake -l で確認（通常はサーバーなので不要）
      echo "{\"success\": true, \"scheduled\": false, \"message\": \"Wake schedule not supported on Linux\"}"
    fi
    ;;

  pmset-set)
    TIME="${1:-}"
    DAYS="${2:-MTWRFSU}"
    if [[ "$OS" == "Darwin" ]]; then
      if ! echo "$TIME" | grep -qE '^[0-2][0-9]:[0-5][0-9]$'; then
        echo "{\"success\": false, \"error\": \"Invalid time format. Use HH:MM\"}"
        exit 1
      fi
      echo "sudo権限が必要です。" >&2
      if sudo pmset repeat wakeorpoweron "$DAYS" "${TIME}:00" 2>&1; then
        echo "{\"success\": true, \"action\": \"set\", \"time\": \"$TIME\", \"days\": \"$DAYS\"}"
      else
        echo "{\"success\": false, \"error\": \"Failed to set wake schedule\"}"
        exit 1
      fi
    else
      echo "{\"success\": false, \"error\": \"Wake schedule not supported on Linux\"}"
      exit 1
    fi
    ;;

  pmset-unset)
    if [[ "$OS" == "Darwin" ]]; then
      echo "sudo権限が必要です。" >&2
      if sudo pmset repeat cancel 2>&1; then
        echo "{\"success\": true, \"action\": \"unset\"}"
      else
        echo "{\"success\": false, \"error\": \"Failed to remove wake schedule\"}"
        exit 1
      fi
    else
      echo "{\"success\": false, \"error\": \"Wake schedule not supported on Linux\"}"
      exit 1
    fi
    ;;

  # ─── ポート管理 ─────────────────────────────────────────────────
  lsof-port)
    PORT="${1:-}"
    if [[ "$OS" == "Darwin" ]]; then
      PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
    else
      PID=$(ss -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
      if [[ -z "$PID" ]]; then
        PID=$(fuser "$PORT/tcp" 2>/dev/null | awk '{print $1}' || true)
      fi
    fi
    echo "${PID:-}"
    ;;

  kill-port)
    PORT="${1:-}"
    if [[ "$OS" == "Darwin" ]]; then
      PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
    else
      PID=$(ss -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
      if [[ -z "$PID" ]]; then
        PID=$(fuser "$PORT/tcp" 2>/dev/null | awk '{print $1}' || true)
      fi
    fi
    if [[ -n "$PID" ]]; then
      kill "$PID" 2>/dev/null || true
      sleep 1
      # まだ残っていれば強制終了
      if [[ "$OS" == "Darwin" ]]; then
        STILL=$(lsof -ti :"$PORT" 2>/dev/null || true)
      else
        STILL=$(ss -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
      fi
      if [[ -n "$STILL" ]]; then
        kill -9 "$STILL" 2>/dev/null || true
      fi
      echo "{\"success\": true, \"pid\": \"$PID\", \"port\": $PORT}"
    else
      echo "{\"success\": true, \"pid\": null, \"port\": $PORT, \"message\": \"No process using port $PORT\"}"
    fi
    ;;

  # ─── 日付ユーティリティ ─────────────────────────────────────────
  date-yesterday)
    if [[ "$OS" == "Darwin" ]]; then
      TZ=Asia/Tokyo date -v-1d +%Y-%m-%d
    else
      TZ=Asia/Tokyo date -d "yesterday" +%Y-%m-%d
    fi
    ;;

  # ─── 環境変数ロード ─────────────────────────────────────────────
  source-env)
    # .zshrc/.bashrc から環境変数を読み込み、key=value形式で出力
    SHELL_RC=""
    if [[ -f "$HOME/.zshrc" ]]; then
      SHELL_RC="$HOME/.zshrc"
    elif [[ -f "$HOME/.bashrc" ]]; then
      SHELL_RC="$HOME/.bashrc"
    fi

    if [[ -n "$SHELL_RC" ]]; then
      # サブシェルでsourceして、対象の環境変数のみ出力
      (
        source "$SHELL_RC" 2>/dev/null || true
        env | grep -E '^(MY_SLACK_OAUTH_TOKEN|SLACK_REFERENCE_BOT_TOKEN|SLACK_REFERENCE_TEAM_ID|GITHUB_TOKEN|NOTION_TOKEN)='
      ) 2>/dev/null || true
    fi
    ;;

  *)
    echo "{\"error\": \"Unknown command: $COMMAND\"}" >&2
    echo "Available commands: caffeinate-start, caffeinate-stop, launchctl, pmset-status, pmset-set, pmset-unset, lsof-port, kill-port, date-yesterday, source-env" >&2
    exit 1
    ;;
esac
