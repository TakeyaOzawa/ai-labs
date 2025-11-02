#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Setup Kubernetes environment with current variables
setup_k8s_env() {
    echo "Setting up Kubernetes environment..."
    WORKSPACE_HOST_PATH=${WORKSPACE_HOST_PATH:-/home/developer/workspace}
    envsubst < k8s/ai-agents/shared-workspace-pv.yaml.template > k8s/ai-agents/shared-workspace-pv.yaml
    echo "  WORKSPACE_HOST_PATH: $WORKSPACE_HOST_PATH"
}

case $1 in
  "start-agents")
    echo "AIエージェントを起動中..."
    setup_k8s_env
    kubectl apply -f k8s/ai-agents/
    echo "AIエージェントを起動しました"
    ;;
  "start-external")
    echo "外部開発環境を起動中..."
    kubectl apply -f k8s/external-env/
    echo "外部開発環境を起動しました"
    ;;
  "start-all")
    echo "全環境を起動中..."
    kubectl apply -f k8s/ai-agents/
    kubectl apply -f k8s/external-env/
    echo "全環境を起動しました"
    ;;
  "stop-agents")
    echo "AIエージェントを停止中..."
    kubectl delete -f k8s/ai-agents/
    echo "AIエージェントを停止しました"
    ;;
  "stop-external")
    echo "外部開発環境を停止中..."
    kubectl delete -f k8s/external-env/
    echo "外部開発環境を停止しました"
    ;;
  "stop-all")
    echo "全環境を停止中..."
    kubectl delete -f k8s/ai-agents/
    kubectl delete -f k8s/external-env/
    echo "全環境を停止しました"
    ;;
  "status")
    echo "=== AIエージェント ==="
    kubectl get pods -n ai-agents
    echo ""
    echo "=== 外部開発環境 ==="
    kubectl get pods -n external-env
    ;;
  "logs")
    if [ -z "$2" ] || [ -z "$3" ]; then
      echo "使用方法: $0 logs <namespace> <app>"
      echo "例: $0 logs ai-agents planner-agent"
      exit 1
    fi
    kubectl logs -n $2 -l app=$3 -f
    ;;
  "start-monitoring")
    echo "監視スタックを起動中..."
    kubectl apply -f k8s/monitoring/
    wait_for_pods "monitoring"
    ;;
  "stop-monitoring")
    echo "監視スタックを停止中..."
    kubectl delete -f k8s/monitoring/ --ignore-not-found=true
    ;;
  "build")
    echo "Dockerイメージをビルド中..."
    ./scripts/build-multiarch.sh
    echo "マルチアーキテクチャDockerイメージのビルドが完了しました"
    ;;
  "build-single")
    echo "シングルアーキテクチャDockerイメージをビルド中..."
    docker build -t agents/common:base -f agents/common/Dockerfile.base .
    docker build -t planner-agent:latest -f agents/planner-agent/Dockerfile .
    docker build -t architect-agent:latest -f agents/architect-agent/Dockerfile .
    docker build -t coder-agent:latest -f agents/coder-agent/Dockerfile .
    docker build -t tester-agent:latest -f agents/tester-agent/Dockerfile .
    echo "シングルアーキテクチャDockerイメージのビルドが完了しました"
    ;;
  *)
    echo "使用方法: $0 {start-agents|start-external|start-monitoring|start-all|stop-agents|stop-external|stop-monitoring|stop-all|status|logs <namespace> <app>|build|build-single}"
    echo ""
    echo "コマンド説明:"
    echo "  start-agents    - AIエージェントを起動"
    echo "  start-external  - 外部開発環境を起動"
    echo "  start-all       - 全環境を起動"
    echo "  stop-agents     - AIエージェントを停止"
    echo "  stop-external   - 外部開発環境を停止"
    echo "  stop-all        - 全環境を停止"
    echo "  status          - 全環境の状態を表示"
    echo "  logs <ns> <app> - 指定したアプリのログを表示"
    echo "  build           - Dockerイメージをビルド"
    ;;
esac
