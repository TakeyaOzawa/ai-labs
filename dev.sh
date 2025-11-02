#!/bin/bash

set -e

# 色付きログ出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[DEV]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[DEV]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[DEV]${NC} $1"
}

# 開発用コマンド
case "${1:-}" in
    "quick-start")
        log_info "Quick development start..."
        ./manage.sh setup
        ./manage.sh build
        ./manage.sh start
        log_success "Development environment ready!"
        ;;
    "rebuild")
        log_info "Rebuilding and restarting..."
        ./manage.sh stop
        ./manage.sh build
        ./manage.sh start
        log_success "Rebuild completed!"
        ;;
    "reset")
        log_warning "Resetting entire environment..."
        ./manage.sh destroy
        ./manage.sh setup
        ./manage.sh build
        ./manage.sh start
        log_success "Environment reset completed!"
        ;;
    "watch-logs")
        service=${2:-""}
        if [ -n "$service" ]; then
            log_info "Watching logs for $service..."
            ./manage.sh logs "$service"
        else
            log_info "Watching all logs..."
            ./manage.sh logs
        fi
        ;;
    "debug")
        service=${2:-"planner-agent"}
        log_info "Opening debug shell in $service..."
        ./manage.sh shell "$service"
        ;;
    "test-agent")
        agent=${2:-"planner-agent"}
        port=""
        case $agent in
            "planner-agent") port="8080" ;;
            "architect-agent") port="8081" ;;
            "coder-agent") port="8082" ;;
            "tester-agent") port="8083" ;;
            *) log_warning "Unknown agent: $agent"; exit 1 ;;
        esac
        
        log_info "Testing $agent on port $port..."
        curl -X POST "http://localhost:$port/mcp" \
            -H "Content-Type: application/json" \
            -d '{"command": "HEALTH_CHECK", "sender": "dev-test"}' | jq .
        ;;
    "monitor")
        log_info "Starting development monitor..."
        watch -n 2 './manage.sh status'
        ;;
    *)
        echo "Development Helper Commands"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  quick-start         Setup, build, and start everything"
        echo "  rebuild             Stop, rebuild, and restart"
        echo "  reset               Complete reset (destroy + setup + build + start)"
        echo "  watch-logs [service] Watch logs for service or all"
        echo "  debug [service]     Open debug shell (default: planner-agent)"
        echo "  test-agent <agent>  Test specific agent endpoint"
        echo "  monitor             Monitor system status"
        echo ""
        echo "Examples:"
        echo "  $0 quick-start"
        echo "  $0 watch-logs planner-agent"
        echo "  $0 debug coder-agent"
        echo "  $0 test-agent architect-agent"
        ;;
esac
