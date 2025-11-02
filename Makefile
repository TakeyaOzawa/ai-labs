.PHONY: help setup build start stop restart destroy status logs shell test clean monitor backup

# デフォルトターゲット
help:
	@echo "AI Development Multi-Agent System"
	@echo "================================="
	@echo ""
	@echo "Quick Commands:"
	@echo "  make setup          Initial setup"
	@echo "  make quick-start    Setup + Build + Start"
	@echo "  make build          Build all images"
	@echo "  make start          Start all services"
	@echo "  make stop           Stop all services"
	@echo "  make restart        Restart all services"
	@echo "  make status         Show system status"
	@echo "  make logs           Show all logs"
	@echo "  make test           Run system tests"
	@echo "  make clean          Clean unused resources"
	@echo "  make destroy        Complete cleanup"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev-rebuild    Quick rebuild and restart"
	@echo "  make dev-reset      Complete reset"
	@echo "  make dev-debug      Open debug shell"
	@echo "  make dev-monitor    Start development monitor"
	@echo ""
	@echo "Monitoring Commands:"
	@echo "  make monitor        System monitoring"
	@echo "  make health         Health check"
	@echo "  make watch          Continuous monitoring"
	@echo ""
	@echo "Backup Commands:"
	@echo "  make backup         Full backup"
	@echo "  make backup-config  Config backup only"
	@echo "  make backup-list    List backups"
	@echo ""
	@echo "Kubernetes Commands:"
	@echo "  make k8s-start      Start K8s environment"
	@echo "  make k8s-stop       Stop K8s environment"
	@echo "  make k8s-status     K8s status"

# 基本コマンド
setup:
	./manage.sh setup

build:
	./manage.sh build

build-multiarch:
	./manage.sh build-multiarch

start:
	./manage.sh start

stop:
	./manage.sh stop

restart:
	./manage.sh restart

destroy:
	./manage.sh destroy

status:
	./manage.sh status

logs:
	./manage.sh logs

test:
	./manage.sh test

clean:
	./manage.sh clean

# 開発コマンド
quick-start:
	./dev.sh quick-start

dev-rebuild:
	./dev.sh rebuild

dev-reset:
	./dev.sh reset

dev-debug:
	./dev.sh debug

dev-monitor:
	./dev.sh monitor

# 監視コマンド
monitor:
	./scripts/monitor.sh status

health:
	./scripts/monitor.sh health

watch:
	./scripts/monitor.sh watch

performance:
	./scripts/monitor.sh performance

alerts:
	./scripts/monitor.sh alerts

# バックアップコマンド
backup:
	./scripts/backup.sh full

backup-config:
	./scripts/backup.sh config

backup-data:
	./scripts/backup.sh data

backup-list:
	./scripts/backup.sh list

backup-cleanup:
	./scripts/backup.sh cleanup

# Kubernetesコマンド
k8s-start:
	./manage.sh k8s-start

k8s-stop:
	./manage.sh k8s-stop

k8s-status:
	./manage.sh k8s-status

# 特定サービスのコマンド
logs-planner:
	./manage.sh logs planner-agent

logs-architect:
	./manage.sh logs architect-agent

logs-coder:
	./manage.sh logs coder-agent

logs-tester:
	./manage.sh logs tester-agent

shell-planner:
	./manage.sh shell planner-agent

shell-architect:
	./manage.sh shell architect-agent

shell-coder:
	./manage.sh shell coder-agent

shell-tester:
	./manage.sh shell tester-agent

# テストコマンド
test-planner:
	./dev.sh test-agent planner-agent

test-architect:
	./dev.sh test-agent architect-agent

test-coder:
	./dev.sh test-agent coder-agent

test-tester:
	./dev.sh test-agent tester-agent
