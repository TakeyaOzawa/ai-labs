FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp + yt-dlp-rajiko プラグイン
# yt-dlp: 2025.02.19以上必須（rajiko plugin互換性）
# yt-dlp-rajiko: v1.11で2026/1/16仕様変更対応済み
RUN pip install --no-cache-dir \
    "yt-dlp>=2025.02.19" \
    "yt-dlp-rajiko>=1.11" \
    pyyaml==6.0.2 \
    "APScheduler>=3.10,<4"

# 共有ボリュームのディレクトリ作成
RUN mkdir -p /data/recordings /data/transcripts /data/summaries /app/state /app/config /app/src

WORKDIR /app

CMD ["sleep", "infinity"]
