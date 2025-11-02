#!/bin/bash

set -e

echo "Initializing Amazon Q configuration..."

# 環境変数を読み込み
if [ -f "/workspace/.env" ]; then
    export $(cat /workspace/.env | grep -v '^#' | xargs)
fi

# .amazonqディレクトリを作成
mkdir -p /workspace/.amazonq/rules
mkdir -p /workspace/.amazonq/logs

# 設定ファイルをテンプレートから生成
if [ -f "/app/.amazonq-template/config.json" ]; then
    envsubst < /app/.amazonq-template/config.json > /workspace/.amazonq/config.json
    echo "Generated Amazon Q config.json"
fi

# ルールファイルをコピー
if [ -d "/app/.amazonq-template/rules" ]; then
    cp -r /app/.amazonq-template/rules/* /workspace/.amazonq/rules/
    echo "Copied Amazon Q rules"
fi

# Slack通知スクリプトをコピー
if [ -f "/app/.amazonq-template/slack-notification.sh" ]; then
    cp /app/.amazonq-template/slack-notification.sh /workspace/.amazonq/slack-notification.sh
    chmod +x /workspace/.amazonq/slack-notification.sh
    echo "Copied Slack notification script"
fi

# Amazon Q CLIの初期設定
if [ -n "$AMAZON_Q_START_URL" ]; then
    echo "Configuring Amazon Q CLI..."
    q configure set start-url "$AMAZON_Q_START_URL" || echo "Q CLI configuration failed"
    q configure set region "${AMAZON_Q_REGION:-us-east-1}" || echo "Q CLI region configuration failed"
fi

echo "Amazon Q configuration initialization complete."
