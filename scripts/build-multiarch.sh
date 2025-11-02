#!/bin/bash

set -e

echo "Building multi-architecture Docker images..."

# Docker Buildxセットアップ
docker buildx create --name multiarch --use --bootstrap || true

# ベースイメージをビルド
echo "Building base image..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -f agents/common/Dockerfile.base \
    -t agents/common:base \
    .

# 各エージェントをビルド
AGENTS=("planner-agent" "architect-agent" "coder-agent" "tester-agent")

for agent in "${AGENTS[@]}"; do
    echo "Building ${agent}..."
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        -f agents/${agent}/Dockerfile \
        -t ${agent}:latest \
        .
done

echo "Multi-architecture build complete!"
echo "Available images:"
docker images | grep -E "(agents/common|planner-agent|architect-agent|coder-agent|tester-agent)"
