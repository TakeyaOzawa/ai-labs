#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f "$(dirname "$0")/../.env" ]; then
    export $(cat "$(dirname "$0")/../.env" | grep -v '^#' | xargs)
fi

AMAZON_Q_URL="${AMAZON_Q_START_URL}"
AMAZON_Q_REGION="${AMAZON_Q_REGION:-us-east-1}"

if [ -z "$AMAZON_Q_URL" ]; then
  echo "Error: AMAZON_Q_START_URL environment variable is not set"
  echo "Please set it in .env file:"
  echo "AMAZON_Q_START_URL=https://your-amazon-q-instance.awsapps.com/start"
  exit 1
fi

echo "Starting Amazon Q Developer..."
echo "URL: $AMAZON_Q_URL"
echo "Region: $AMAZON_Q_REGION"

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$AMAZON_Q_URL"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open > /dev/null; then
        xdg-open "$AMAZON_Q_URL"
    elif command -v gnome-open > /dev/null; then
        gnome-open "$AMAZON_Q_URL"
    else
        echo "Please open the following URL in your browser:"
        echo "$AMAZON_Q_URL"
    fi
else
    echo "Please open the following URL in your browser:"
    echo "$AMAZON_Q_URL"
fi
