#!/bin/bash

echo "Initializing TesterAgent..."

# MySQL接続テスト
if [ -n "$MYSQL_HOST" ]; then
    echo "Testing MySQL connection..."
    python3 -c "
import pymysql
import os
try:
    conn = pymysql.connect(
        host=os.getenv('MYSQL_HOST'),
        user='testuser',
        password='testpass',
        database='testdb'
    )
    conn.close()
    print('MySQL connection: OK')
except Exception as e:
    print(f'MySQL connection failed: {e}')
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

# Nginx接続テスト
if [ -n "$NGINX_HOST" ]; then
    echo "Testing Nginx connection..."
    curl -s -f "http://$NGINX_HOST/health" > /dev/null && echo "Nginx connection: OK" || echo "Nginx connection failed"
fi

# Amazon Q CLI テスト
echo "Testing Amazon Q CLI..."
q --version || echo "Amazon Q CLI not available"

# AWS CLI テスト
echo "Testing AWS CLI..."
aws --version || echo "AWS CLI not available"

echo "TesterAgent initialization complete."
