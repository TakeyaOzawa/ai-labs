FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY agents/architect-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/architect-agent/ .
COPY agents/common/ ./common/

RUN mkdir -p /workspace

EXPOSE 8081

CMD ["python", "logic.py"]
