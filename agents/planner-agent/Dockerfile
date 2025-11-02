FROM agents/common:base

# エージェント固有の依存関係をインストール
COPY agents/planner-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# エージェント固有のコードをコピー
COPY agents/planner-agent/ .
COPY agents/common/ ./common/

# 役割設定をコピー
COPY agents/common/roles/ /app/roles/

# エージェント固有の初期化スクリプト
COPY agents/planner-agent/init-planner.sh /app/init-planner.sh
RUN chmod +x /app/init-planner.sh

# 設定ファイルをコピー
COPY agents/planner-agent/planner_config.yaml /app/config/

EXPOSE 8080

CMD ["python", "logic.py"]
