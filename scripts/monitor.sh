#!/bin/bash

set -e

# システム監視とメトリクス収集

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[MONITOR]${NC} $1"
}

# リソース使用量を取得
get_resource_usage() {
    echo "=== System Resource Usage ==="
    
    # Docker統計
    echo "Docker Container Stats:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | head -10
    
    echo ""
    echo "Docker System Usage:"
    docker system df
    
    echo ""
    echo "Host System:"
    echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)% used"
    echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"
}

# エージェント健康状態チェック
check_agent_health() {
    echo "=== Agent Health Status ==="
    
    local agents=("planner-agent:8080" "architect-agent:8081" "coder-agent:8082" "tester-agent:8083")
    
    for agent_port in "${agents[@]}"; do
        IFS=':' read -r agent port <<< "$agent_port"
        
        if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $agent (port $port) - Healthy"
        else
            echo -e "${RED}✗${NC} $agent (port $port) - Unhealthy"
        fi
    done
}

# ログエラー監視
check_log_errors() {
    echo "=== Recent Log Errors ==="
    
    # 過去5分のエラーログを検索
    docker-compose logs --since=5m 2>&1 | grep -i "error\|exception\|failed" | tail -10 || echo "No recent errors found"
}

# ネットワーク接続チェック
check_network() {
    echo "=== Network Connectivity ==="
    
    # 外部サービス接続チェック
    services=("mysql:3306" "redis:6379" "postgres-history:5432")
    
    for service in "${services[@]}"; do
        IFS=':' read -r host port <<< "$service"
        
        if docker-compose exec -T planner-agent nc -z "$host" "$port" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $service - Connected"
        else
            echo -e "${RED}✗${NC} $service - Connection failed"
        fi
    done
}

# パフォーマンスメトリクス
get_performance_metrics() {
    echo "=== Performance Metrics ==="
    
    # レスポンス時間測定
    for port in 8080 8081 8082 8083; do
        response_time=$(curl -o /dev/null -s -w "%{time_total}" "http://localhost:$port/health" 2>/dev/null || echo "N/A")
        agent_name=""
        case $port in
            8080) agent_name="planner-agent" ;;
            8081) agent_name="architect-agent" ;;
            8082) agent_name="coder-agent" ;;
            8083) agent_name="tester-agent" ;;
        esac
        echo "$agent_name response time: ${response_time}s"
    done
}

# 継続監視モード
continuous_monitor() {
    log_info "Starting continuous monitoring (Ctrl+C to stop)..."
    
    while true; do
        clear
        echo "AI Development Multi-Agent System Monitor"
        echo "=========================================="
        echo "$(date)"
        echo ""
        
        get_resource_usage
        echo ""
        check_agent_health
        echo ""
        check_network
        echo ""
        get_performance_metrics
        echo ""
        check_log_errors
        
        sleep 30
    done
}

# アラート設定
check_alerts() {
    echo "=== System Alerts ==="
    
    # CPU使用率チェック
    cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" | sed 's/%//' | awk '{sum+=$1} END {print sum/NR}')
    if [ $(echo "$cpu_usage > 80" | awk '{print ($1 > $2)}') -eq 1 ]; then
        echo -e "${RED}⚠${NC} High CPU usage: ${cpu_usage}%"
    fi
    
    # メモリ使用率チェック
    memory_usage=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}')
    if [ $(echo "$memory_usage > 80" | awk '{print ($1 > $2)}') -eq 1 ]; then
        echo -e "${RED}⚠${NC} High memory usage: ${memory_usage}%"
    fi
    
    # ディスク使用率チェック
    disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}⚠${NC} High disk usage: ${disk_usage}%"
    fi
    
    # 不健康なエージェントチェック
    unhealthy_count=0
    for port in 8080 8081 8082 8083; do
        if ! curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
            ((unhealthy_count++))
        fi
    done
    
    if [ "$unhealthy_count" -gt 0 ]; then
        echo -e "${RED}⚠${NC} $unhealthy_count agent(s) are unhealthy"
    fi
    
    if [ "$unhealthy_count" -eq 0 ] && \
       [ $(echo "$cpu_usage <= 80" | awk '{print ($1 <= $2)}') -eq 1 ] && \
       [ $(echo "$memory_usage <= 80" | awk '{print ($1 <= $2)}') -eq 1 ] && \
       [ "$disk_usage" -le 80 ]; then
        echo -e "${GREEN}✓${NC} All systems normal"
    fi
}

# メイン処理
case "${1:-}" in
    "status")
        get_resource_usage
        echo ""
        check_agent_health
        ;;
    "health")
        check_agent_health
        echo ""
        check_network
        ;;
    "performance")
        get_performance_metrics
        ;;
    "logs")
        check_log_errors
        ;;
    "alerts")
        check_alerts
        ;;
    "watch")
        continuous_monitor
        ;;
    *)
        echo "System Monitor Commands"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  status       Show system resource usage"
        echo "  health       Check agent health and network"
        echo "  performance  Show performance metrics"
        echo "  logs         Check recent log errors"
        echo "  alerts       Check system alerts"
        echo "  watch        Continuous monitoring mode"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  $0 watch"
        ;;
esac
