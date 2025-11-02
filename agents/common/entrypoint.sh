#!/bin/bash

set -e

echo "Starting AI Agent Container..."
echo "Agent Type: ${AGENT_TYPE:-unknown}"
echo "Platform: $(uname -m)"

# 役割設定を読み込み
python3 -c "
from role_config import RoleManager
import sys
import os

try:
    role_manager = RoleManager()
    role_manager.setup_environment()
    print(f'Role: {role_manager.role.name}')
    print(f'Description: {role_manager.role.description}')
    print(f'Capabilities: {role_manager.role.capabilities}')
except Exception as e:
    print(f'Error loading role config: {e}')
    sys.exit(1)
"

# Amazon Q設定を初期化
if [ -f "/app/.amazonq-template/init-amazonq.sh" ]; then
    echo "Initializing Amazon Q configuration..."
    bash /app/.amazonq-template/init-amazonq.sh
fi

# AWS設定
if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Configuring AWS CLI..."
    aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID"
    aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY"
    aws configure set default.region "${AWS_DEFAULT_REGION:-us-east-1}"
fi

# ワークスペースディレクトリに移動
cd /workspace

# エージェント固有の初期化スクリプトを実行
if [ -f "/app/init-${AGENT_TYPE}.sh" ]; then
    echo "Running agent-specific initialization..."
    bash "/app/init-${AGENT_TYPE}.sh"
fi

# メインアプリケーションを起動
echo "Starting main application..."
exec "$@"
