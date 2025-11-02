FROM agents/common:base

# エージェント固有の依存関係をインストール
COPY agents/tester-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# エージェント固有のコードをコピー
COPY agents/tester-agent/ .
COPY agents/common/ ./common/

# 役割設定をコピー
COPY agents/common/roles/ /app/roles/

# エージェント固有の初期化スクリプト
COPY agents/tester-agent/init-tester.sh /app/init-tester.sh
RUN chmod +x /app/init-tester.sh

EXPOSE 8083

CMD ["python", "logic.py"]
