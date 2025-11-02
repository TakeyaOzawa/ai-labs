#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values
WORKSPACE_HOST_PATH=${WORKSPACE_HOST_PATH:-/home/developer/workspace}
AMAZON_Q_START_URL=${AMAZON_Q_START_URL:-https://your-amazon-q-instance.awsapps.com/start}
AMAZON_Q_REGION=${AMAZON_Q_REGION:-us-east-1}
NOTION_DATABASE_ID=${NOTION_DATABASE_ID:-your-database-id-here}
NOTION_WORKSPACE_URL=${NOTION_WORKSPACE_URL:-https://www.notion.so/your-workspace}

echo "Setting up Kubernetes environment with:"
echo "  WORKSPACE_HOST_PATH: $WORKSPACE_HOST_PATH"
echo "  AMAZON_Q_START_URL: $AMAZON_Q_START_URL"
echo "  AMAZON_Q_REGION: $AMAZON_Q_REGION"
echo "  NOTION_DATABASE_ID: $NOTION_DATABASE_ID"
echo "  NOTION_WORKSPACE_URL: $NOTION_WORKSPACE_URL"

# Update PersistentVolume with environment variable
envsubst < k8s/ai-agents/shared-workspace-pv.yaml.template > k8s/ai-agents/shared-workspace-pv.yaml

# Update Amazon Q ConfigMap
cat > k8s/ai-agents/amazon-q-config.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: amazon-q-config
  namespace: ai-agents
data:
  start_url: "$AMAZON_Q_START_URL"
  region: "$AMAZON_Q_REGION"
---
apiVersion: v1
kind: Secret
metadata:
  name: slack-secret
  namespace: ai-agents
type: Opaque
data:
  oauth_token: $(echo -n "$AMAZON_Q_SLACK_OAUTH_TOKEN" | base64 -w 0)
  user_id: $(echo -n "$AMAZON_Q_SLACK_USER_ID" | base64 -w 0)
EOF

# Update Notion ConfigMap and Secret
cat > k8s/ai-agents/notion-config.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: notion-config
  namespace: ai-agents
data:
  database_id: "$NOTION_DATABASE_ID"
  workspace_url: "$NOTION_WORKSPACE_URL"
---
apiVersion: v1
kind: Secret
metadata:
  name: notion-secret
  namespace: ai-agents
type: Opaque
data:
  api_token: $(echo -n "$NOTION_API_TOKEN" | base64 -w 0)
EOF

echo "Kubernetes configuration updated successfully!"
