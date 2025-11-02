FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY agents/coder-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/coder-agent/ .
COPY agents/common/ ./common/

RUN mkdir -p /workspace

EXPOSE 8082

CMD ["python", "logic.py"]
