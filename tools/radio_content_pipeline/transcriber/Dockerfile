FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# faster-whisper + 依存パッケージ
RUN pip install --no-cache-dir \
    faster-whisper \
    anthropic \
    pyyaml==6.0.2

# 共有ボリュームのディレクトリ作成
RUN mkdir -p /data/recordings /data/transcripts /data/summaries /app/state /app/config /app/src

WORKDIR /app

CMD ["python3", "src/transcriber.py"]
