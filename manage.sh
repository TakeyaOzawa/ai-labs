#!/bin/bash

set -e

# 色付きログ出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 環境変数を読み込み
load_env() {
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
        log_info "Environment variables loaded from .env"
    else
        log_warning ".env file not found, using default values"
    fi
}

# 使用方法を表示
show_usage() {
    echo "AI Development Multi-Agent System Management"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build                 Build all Docker images"
    echo "  build-multiarch      Build multi-architecture images"
    echo "  start                Start all services"
    echo "  stop                 Stop all services"
    echo "  restart              Restart all services"
    echo "  destroy              Stop and remove all containers, images, volumes"
    echo "  status               Show status of all services"
    echo "  logs [service]       Show logs (optionally for specific service)"
    echo "  shell <service>      Open shell in service container"
    echo "  test                 Run system tests"
    echo "  clean                Clean up unused Docker resources"
    echo "  setup                Initial setup (copy .env.example to .env)"
    echo ""
    echo "Kubernetes Commands:"
    echo "  k8s-start           Start Kubernetes environment"
    echo "  k8s-stop            Stop Kubernetes environment"
    echo "  k8s-status          Show Kubernetes status"
    echo "  k8s-logs <pod>      Show Kubernetes pod logs"
    echo ""
    echo "Examples:"
    echo "  $0 setup            # Initial setup"
    echo "  $0 build            # Build all images"
    echo "  $0 start            # Start all services"
    echo "  $0 logs planner-agent  # Show planner-agent logs"
    echo "  $0 shell coder-agent   # Open shell in coder-agent"
    echo "  $0 destroy          # Complete cleanup"
}

# 初期セットアップ
setup() {
    log_info "Setting up AI Development Multi-Agent System..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        log_success "Created .env file from template"
        log_warning "Please edit .env file with your actual configuration values"
    else
        log_info ".env file already exists"
    fi
    
    # 必要なディレクトリを作成
    mkdir -p .amazonq/logs
    mkdir -p project_root
    
    log_success "Setup completed"
}

# Docker Composeビルド
build() {
    log_info "Building Docker images..."
    load_env
    
    # ベースイメージをビルド
    docker build -t agents/common:base -f agents/common/Dockerfile.base .
    
    # 各エージェントをビルド
    docker-compose build
    
    log_success "All Docker images built successfully"
}

# マルチアーキテクチャビルド
build_multiarch() {
    log_info "Building multi-architecture Docker images..."
    load_env
    
    ./scripts/build-multiarch.sh
    
    log_success "Multi-architecture images built successfully"
}

# サービス開始
start() {
    log_info "Starting AI Development Multi-Agent System..."
    load_env
    
    # .amazonqディレクトリが存在しない場合は作成
    if [ ! -d .amazonq ]; then
        mkdir -p .amazonq/logs
        log_info "Created .amazonq directory"
    fi
    
    docker-compose up -d
    
    log_success "All services started"
    
    # サービスの起動を待機
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # ヘルスチェック
    health_check
}

# サービス停止
stop() {
    log_info "Stopping all services..."
    
    docker-compose down
    
    log_success "All services stopped"
}

# サービス再起動
restart() {
    log_info "Restarting all services..."
    
    stop
    sleep 5
    start
    
    log_success "All services restarted"
}

# 完全破棄
destroy() {
    log_warning "This will destroy all containers, images, and volumes!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Destroying all resources..."
        
        # コンテナとボリュームを停止・削除
        docker-compose down -v --remove-orphans
        
        # イメージを削除
        docker rmi $(docker images -q --filter "reference=*agent*") 2>/dev/null || true
        docker rmi agents/common:base 2>/dev/null || true
        
        # 未使用リソースをクリーンアップ
        docker system prune -f
        
        log_success "All resources destroyed"
    else
        log_info "Destroy cancelled"
    fi
}

# ステータス確認
status() {
    log_info "Checking service status..."
    
    echo ""
    echo "=== Docker Compose Services ==="
    docker-compose ps
    
    echo ""
    echo "=== Docker Images ==="
    docker images | grep -E "(agent|common)" || echo "No agent images found"
    
    echo ""
    echo "=== System Resources ==="
    docker system df
}

# ログ表示
show_logs() {
    local service=$1
    
    if [ -n "$service" ]; then
        log_info "Showing logs for $service..."
        docker-compose logs -f "$service"
    else
        log_info "Showing logs for all services..."
        docker-compose logs -f
    fi
}

# シェル接続
shell() {
    local service=$1
    
    if [ -z "$service" ]; then
        log_error "Service name required"
        echo "Available services: planner-agent, architect-agent, coder-agent, tester-agent"
        exit 1
    fi
    
    log_info "Opening shell in $service..."
    docker-compose exec "$service" /bin/bash
}

# ヘルスチェック
health_check() {
    log_info "Performing health checks..."
    
    local services=("planner-agent:8080" "architect-agent:8081" "coder-agent:8082" "tester-agent:8083")
    
    for service_port in "${services[@]}"; do
        IFS=':' read -r service port <<< "$service_port"
        
        if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
            log_success "$service is healthy"
        else
            log_warning "$service health check failed (port $port)"
        fi
    done
}

# システムテスト
test() {
    log_info "Running system tests..."
    
    # 基本的な接続テスト
    health_check
    
    # エージェント間通信テスト
    log_info "Testing agent communication..."
    
    # PlannerAgentにテストリクエストを送信
    if curl -s -X POST "http://localhost:8080/mcp" \
        -H "Content-Type: application/json" \
        -d '{"command": "HEALTH_CHECK", "sender": "test"}' > /dev/null; then
        log_success "Agent communication test passed"
    else
        log_error "Agent communication test failed"
    fi
}

# クリーンアップ
clean() {
    log_info "Cleaning up unused Docker resources..."
    
    docker system prune -f
    docker volume prune -f
    
    log_success "Cleanup completed"
}

# Kubernetes管理
k8s_start() {
    log_info "Starting Kubernetes environment..."
    load_env
    
    ./manage-k8s.sh start-all
    
    log_success "Kubernetes environment started"
}

k8s_stop() {
    log_info "Stopping Kubernetes environment..."
    
    ./manage-k8s.sh stop-all
    
    log_success "Kubernetes environment stopped"
}

k8s_status() {
    log_info "Checking Kubernetes status..."
    
    ./manage-k8s.sh status
}

k8s_logs() {
    local pod=$1
    
    if [ -z "$pod" ]; then
        log_error "Pod name required"
        exit 1
    fi
    
    ./manage-k8s.sh logs ai-agents "$pod"
}

# メイン処理
main() {
    case "${1:-}" in
        "setup")
            setup
            ;;
        "build")
            build
            ;;
        "build-multiarch")
            build_multiarch
            ;;
        "start")
            start
            ;;
        "stop")
            stop
            ;;
        "restart")
            restart
            ;;
        "destroy")
            destroy
            ;;
        "status")
            status
            ;;
        "logs")
            show_logs "$2"
            ;;
        "shell")
            shell "$2"
            ;;
        "test")
            test
            ;;
        "clean")
            clean
            ;;
        "k8s-start")
            k8s_start
            ;;
        "k8s-stop")
            k8s_stop
            ;;
        "k8s-status")
            k8s_status
            ;;
        "k8s-logs")
            k8s_logs "$2"
            ;;
        "help"|"--help"|"-h"|"")
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
