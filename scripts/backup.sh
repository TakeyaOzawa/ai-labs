#!/bin/bash

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[BACKUP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[BACKUP]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[BACKUP]${NC} $1"
}

# バックアップディレクトリ作成
create_backup_dir() {
    mkdir -p "$BACKUP_DIR/$TIMESTAMP"
    log_info "Created backup directory: $BACKUP_DIR/$TIMESTAMP"
}

# 設定ファイルのバックアップ
backup_config() {
    log_info "Backing up configuration files..."
    
    local backup_path="$BACKUP_DIR/$TIMESTAMP/config"
    mkdir -p "$backup_path"
    
    # 環境設定
    [ -f .env ] && cp .env "$backup_path/"
    
    # Docker設定
    cp docker-compose.yml "$backup_path/"
    
    # Amazon Q設定
    [ -d .amazonq ] && cp -r .amazonq "$backup_path/"
    
    # エージェント設定
    cp -r agents/ "$backup_path/"
    cp -r k8s/ "$backup_path/"
    
    log_success "Configuration files backed up"
}

# データベースのバックアップ
backup_databases() {
    log_info "Backing up databases..."
    
    local backup_path="$BACKUP_DIR/$TIMESTAMP/data"
    mkdir -p "$backup_path"
    
    # PostgreSQL バックアップ
    if docker-compose ps postgres-history | grep -q "Up"; then
        log_info "Backing up PostgreSQL..."
        docker-compose exec -T postgres-history pg_dump -U planner dev_history > "$backup_path/postgres_backup.sql"
        log_success "PostgreSQL backup completed"
    else
        log_warning "PostgreSQL container not running, skipping backup"
    fi
    
    # MySQL バックアップ
    if docker-compose ps mysql | grep -q "Up"; then
        log_info "Backing up MySQL..."
        docker-compose exec -T mysql mysqldump -u root -prootpass testdb > "$backup_path/mysql_backup.sql"
        log_success "MySQL backup completed"
    else
        log_warning "MySQL container not running, skipping backup"
    fi
    
    # Redis バックアップ
    if docker-compose ps redis | grep -q "Up"; then
        log_info "Backing up Redis..."
        docker-compose exec -T redis redis-cli BGSAVE
        sleep 2
        docker cp $(docker-compose ps -q redis):/data/dump.rdb "$backup_path/redis_backup.rdb"
        log_success "Redis backup completed"
    else
        log_warning "Redis container not running, skipping backup"
    fi
}

# プロジェクトファイルのバックアップ
backup_project() {
    log_info "Backing up project files..."
    
    local backup_path="$BACKUP_DIR/$TIMESTAMP/project"
    mkdir -p "$backup_path"
    
    # プロジェクトルート
    [ -d project_root ] && cp -r project_root "$backup_path/"
    
    # ドキュメント
    [ -d docs ] && cp -r docs "$backup_path/"
    
    # スクリプト
    cp -r scripts "$backup_path/"
    
    # 管理ファイル
    cp manage.sh "$backup_path/"
    cp manage-k8s.sh "$backup_path/"
    [ -f dev.sh ] && cp dev.sh "$backup_path/"
    
    log_success "Project files backed up"
}

# 完全バックアップ
full_backup() {
    log_info "Starting full backup..."
    
    create_backup_dir
    backup_config
    backup_databases
    backup_project
    
    # バックアップ情報ファイル作成
    cat > "$BACKUP_DIR/$TIMESTAMP/backup_info.txt" << EOF
Backup Information
==================
Timestamp: $TIMESTAMP
Date: $(date)
System: $(uname -a)
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Services Status at Backup Time:
$(docker-compose ps)

Backup Contents:
- Configuration files (.env, docker-compose.yml, agents/, k8s/)
- Amazon Q settings (.amazonq/)
- Database dumps (PostgreSQL, MySQL, Redis)
- Project files (project_root/, docs/, scripts/)
- Management scripts
EOF
    
    # バックアップを圧縮
    log_info "Compressing backup..."
    cd "$BACKUP_DIR"
    tar -czf "backup_${TIMESTAMP}.tar.gz" "$TIMESTAMP"
    rm -rf "$TIMESTAMP"
    cd - > /dev/null
    
    log_success "Full backup completed: $BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"
}

# バックアップ復元
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_warning "Available backups:"
        ls -la "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "No backups found"
        echo ""
        echo "Usage: $0 restore <backup_file>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_warning "Backup file not found: $backup_file"
        exit 1
    fi
    
    log_warning "This will overwrite current configuration and data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    log_info "Restoring from backup: $backup_file"
    
    # サービス停止
    ./manage.sh stop
    
    # バックアップ展開
    local restore_dir="/tmp/restore_$$"
    mkdir -p "$restore_dir"
    tar -xzf "$backup_file" -C "$restore_dir"
    
    local backup_name=$(basename "$backup_file" .tar.gz | sed 's/backup_//')
    local backup_path="$restore_dir/$backup_name"
    
    # 設定ファイル復元
    if [ -d "$backup_path/config" ]; then
        log_info "Restoring configuration files..."
        [ -f "$backup_path/config/.env" ] && cp "$backup_path/config/.env" .
        cp "$backup_path/config/docker-compose.yml" .
        [ -d "$backup_path/config/.amazonq" ] && cp -r "$backup_path/config/.amazonq" .
        cp -r "$backup_path/config/agents" .
        cp -r "$backup_path/config/k8s" .
    fi
    
    # プロジェクトファイル復元
    if [ -d "$backup_path/project" ]; then
        log_info "Restoring project files..."
        [ -d "$backup_path/project/project_root" ] && cp -r "$backup_path/project/project_root" .
        [ -d "$backup_path/project/docs" ] && cp -r "$backup_path/project/docs" .
        cp -r "$backup_path/project/scripts" .
        cp "$backup_path/project/manage.sh" .
        cp "$backup_path/project/manage-k8s.sh" .
        [ -f "$backup_path/project/dev.sh" ] && cp "$backup_path/project/dev.sh" .
    fi
    
    # サービス再起動
    ./manage.sh start
    
    # データベース復元
    if [ -d "$backup_path/data" ]; then
        log_info "Restoring databases..."
        sleep 10  # サービス起動待機
        
        # PostgreSQL復元
        if [ -f "$backup_path/data/postgres_backup.sql" ]; then
            docker-compose exec -T postgres-history psql -U planner -d dev_history < "$backup_path/data/postgres_backup.sql"
            log_success "PostgreSQL restored"
        fi
        
        # MySQL復元
        if [ -f "$backup_path/data/mysql_backup.sql" ]; then
            docker-compose exec -T mysql mysql -u root -prootpass testdb < "$backup_path/data/mysql_backup.sql"
            log_success "MySQL restored"
        fi
        
        # Redis復元
        if [ -f "$backup_path/data/redis_backup.rdb" ]; then
            docker-compose stop redis
            docker cp "$backup_path/data/redis_backup.rdb" $(docker-compose ps -q redis):/data/dump.rdb
            docker-compose start redis
            log_success "Redis restored"
        fi
    fi
    
    # クリーンアップ
    rm -rf "$restore_dir"
    
    log_success "Restore completed successfully"
}

# バックアップ一覧表示
list_backups() {
    log_info "Available backups:"
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -la "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "No backups found"
    else
        echo "Backup directory not found: $BACKUP_DIR"
    fi
}

# 古いバックアップ削除
cleanup_old_backups() {
    local keep_days=${1:-7}
    
    log_info "Cleaning up backups older than $keep_days days..."
    
    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$keep_days -delete
        log_success "Old backups cleaned up"
    fi
}

# メイン処理
case "${1:-}" in
    "full")
        full_backup
        ;;
    "config")
        create_backup_dir
        backup_config
        log_success "Configuration backup completed: $BACKUP_DIR/$TIMESTAMP"
        ;;
    "data")
        create_backup_dir
        backup_databases
        log_success "Database backup completed: $BACKUP_DIR/$TIMESTAMP"
        ;;
    "restore")
        restore_backup "$2"
        ;;
    "list")
        list_backups
        ;;
    "cleanup")
        cleanup_old_backups "$2"
        ;;
    *)
        echo "Backup and Restore Commands"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  full                 Complete backup (config + data + project)"
        echo "  config               Backup configuration files only"
        echo "  data                 Backup databases only"
        echo "  restore <file>       Restore from backup file"
        echo "  list                 List available backups"
        echo "  cleanup [days]       Remove backups older than N days (default: 7)"
        echo ""
        echo "Examples:"
        echo "  $0 full"
        echo "  $0 restore backups/backup_20231102_143022.tar.gz"
        echo "  $0 cleanup 30"
        ;;
esac
