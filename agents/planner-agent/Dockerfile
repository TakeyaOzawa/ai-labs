FROM node:22-slim

# OSパッケージのインストール: Python, pip, Git
RUN apt-get update && apt-get install -y \
    python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 共通モジュールをコピー
COPY ./agents/common /app/common

# エージェントのロジックをコピー
COPY ./agents/planner-agent/logic.py /app/agent_logic/planner.py

# 起動コマンド
CMD ["uvicorn", "agent_logic.planner:app", "--host", "0.0.0.0", "--port", "8080"]
