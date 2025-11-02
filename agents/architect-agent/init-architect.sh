#!/bin/bash

echo "Initializing ArchitectAgent..."

# Amazon Q CLI テスト
echo "Testing Amazon Q CLI..."
q --version || echo "Amazon Q CLI not available"

# AWS CLI テスト
echo "Testing AWS CLI..."
aws --version || echo "AWS CLI not available"

echo "ArchitectAgent initialization complete."
