#!/bin/bash

echo "Initializing PlannerAgent..."

# データベース接続テスト
if [ -n "$POSTGRES_HOST" ]; then
    echo "Testing PostgreSQL connection..."
    python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )
    conn.close()
    print('PostgreSQL connection: OK')
except Exception as e:
    print(f'PostgreSQL connection failed: {e}')
"
fi

# Redis接続テスト
if [ -n "$REDIS_HOST" ]; then
    echo "Testing Redis connection..."
    python3 -c "
import redis
import os
try:
    r = redis.Redis(host=os.getenv('REDIS_HOST'), port=6379, decode_responses=True)
    r.ping()
    print('Redis connection: OK')
except Exception as e:
    print(f'Redis connection failed: {e}')
"
fi

# Amazon Q CLI テスト
echo "Testing Amazon Q CLI..."
q --version || echo "Amazon Q CLI not available"

# AWS CLI テスト
echo "Testing AWS CLI..."
aws --version || echo "AWS CLI not available"

echo "PlannerAgent initialization complete."
