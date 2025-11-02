FROM node:22-slim

# OSパッケージのインストール: Python, pip, Git, MySQL client
RUN apt-get update && apt-get install -y \
    python3 python3-pip git \
    mysql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 共通モジュールをコピー
COPY ./agents/common /app/common

# エージェントのロジックをコピー
COPY ./agents/coder-agent/logic.py /app/agent_logic/coder.py

# project_rootディレクトリを作成
RUN mkdir -p /app/project_root

# 起動コマンド
CMD ["uvicorn", "agent_logic.coder:app", "--host", "0.0.0.0", "--port", "8082"]
