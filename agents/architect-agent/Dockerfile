FROM agents/common:base

# エージェント固有の依存関係をインストール
COPY agents/architect-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# エージェント固有のコードをコピー
COPY agents/architect-agent/ .
COPY agents/common/ ./common/

# 役割設定をコピー
COPY agents/common/roles/ /app/roles/

# エージェント固有の初期化スクリプト
COPY agents/architect-agent/init-architect.sh /app/init-architect.sh
RUN chmod +x /app/init-architect.sh

EXPOSE 8081

CMD ["python", "logic.py"]
