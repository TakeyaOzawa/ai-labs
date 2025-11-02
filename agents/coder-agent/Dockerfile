FROM agents/common:base

# エージェント固有の依存関係をインストール
COPY agents/coder-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# エージェント固有のコードをコピー
COPY agents/coder-agent/ .
COPY agents/common/ ./common/

# 役割設定をコピー
COPY agents/common/roles/ /app/roles/

# エージェント固有の初期化スクリプト
COPY agents/coder-agent/init-coder.sh /app/init-coder.sh
RUN chmod +x /app/init-coder.sh

EXPOSE 8082

CMD ["python", "logic.py"]
