# AI Development Multi-Agent System

マルチエージェントシステムによる自動開発プラットフォーム

## 🏗️ システム構成

### AIエージェント
- **PlannerAgent** (Port: 8080) - タスク計画・指示
- **ArchitectAgent** (Port: 8081) - システム設計
- **CoderAgent** (Port: 8082) - コード生成・修正
- **TesterAgent** (Port: 8083) - テスト実行・検証

### 外部開発環境
- **MySQL** (Port: 3306) - データベース
- **Redis** (Port: 6379) - キャッシュ
- **PHP-FPM** (Port: 9000) - アプリケーション実行
- **Nginx** (Port: 8080) - Webサーバー

## 🚀 クイックスタート

### Docker Composeを使用した起動

```bash
# 1. Dockerイメージをビルド
./manage-k8s.sh build

# 2. 全サービスを起動
docker-compose up -d

# 3. 状態確認
docker-compose ps

# 4. ログ確認
docker-compose logs -f planner-agent
```

### Kubernetesを使用した起動

```bash
# 1. Dockerイメージをビルド
./manage-k8s.sh build

# 2. 全環境を起動
./manage-k8s.sh start-all

# 3. 状態確認
./manage-k8s.sh status

# 4. ログ確認
./manage-k8s.sh logs ai-agents planner-agent
```

## 📋 使用方法

### 1. 開発タスクの開始

PlannerAgentにHTTP POSTリクエストを送信してタスクを開始：

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "command": "INITIAL_TASK",
    "sender": "User",
    "payload": {
      "requirements": "ユーザー認証システムを実装してください",
      "constraints": ["PHP 8.2", "MySQL 8.0", "Redis"]
    }
  }'
```

### 2. エージェント間通信の確認

各エージェントのヘルスチェック：

```bash
# PlannerAgent
curl http://localhost:8080/health

# ArchitectAgent
curl http://localhost:8081/health

# CoderAgent
curl http://localhost:8082/health

# TesterAgent
curl http://localhost:8083/health
```

### 3. 外部環境の確認

```bash
# Nginx (Webサーバー)
curl http://localhost:8080/health

# MySQL接続テスト
mysql -h localhost -P 3306 -u testuser -ptestpass testdb -e "SELECT 1;"

# Redis接続テスト
redis-cli -h localhost -p 6379 ping
```

## 🔧 管理コマンド

### Kubernetes環境

```bash
# 全環境起動
./manage-k8s.sh start-all

# AIエージェントのみ起動
./manage-k8s.sh start-agents

# 外部開発環境のみ起動
./manage-k8s.sh start-external

# 状態確認
./manage-k8s.sh status

# ログ確認
./manage-k8s.sh logs ai-agents planner-agent

# 全環境停止
./manage-k8s.sh stop-all

# Dockerイメージビルド
./manage-k8s.sh build
```

### Docker Compose環境

```bash
# 起動
docker-compose up -d

# 停止
docker-compose down

# ログ確認
docker-compose logs -f <service-name>

# 再ビルド
docker-compose build

# 状態確認
docker-compose ps
```

## 📁 プロジェクト構造

```
ai-dev-project/
├── agents/                    # AIエージェント実装
│   ├── common/               # 共通モジュール
│   ├── planner-agent/        # PlannerAgent
│   ├── architect-agent/      # ArchitectAgent
│   ├── coder-agent/          # CoderAgent
│   └── tester-agent/         # TesterAgent
├── k8s/                      # Kubernetesマニフェスト
│   ├── ai-agents/           # AIエージェント用
│   └── external-env/        # 外部開発環境用
├── project_root/            # 開発対象コードベース
├── cdk/                     # AWS CDK (未実装)
├── docker-compose.yml       # Docker Compose設定
├── manage-k8s.sh           # 管理スクリプト
└── README.md               # このファイル
```

## 🔄 ワークフロー

1. **ユーザー** → **PlannerAgent**: 開発要求を送信
2. **PlannerAgent** → **ArchitectAgent**: 設計を依頼
3. **ArchitectAgent** → **CoderAgent**: コード生成を依頼
4. **CoderAgent** → **TesterAgent**: テスト実行を依頼
5. **TesterAgent** → **CoderAgent**: テスト結果を報告
6. **CoderAgent** → **PlannerAgent**: 完了報告
7. **PlannerAgent** → **ユーザー**: 最終結果を報告

## 🐛 トラブルシューティング

### よくある問題

1. **エージェント間通信エラー**
   ```bash
   # DNS解決確認
   kubectl exec -n ai-agents deployment/planner-agent -- nslookup architect-agent.ai-agents.svc.cluster.local
   ```

2. **外部環境接続エラー**
   ```bash
   # MySQL接続確認
   kubectl exec -n ai-agents deployment/coder-agent -- mysql -h mysql.external-env.svc.cluster.local -u testuser -ptestpass -e "SELECT 1;"
   ```

3. **PVC マウントエラー**
   ```bash
   # PVC状態確認
   kubectl get pvc -n ai-agents
   kubectl get pvc -n external-env
   ```

### ログ確認

```bash
# 全エージェントのログ
kubectl logs -n ai-agents -l app=planner-agent
kubectl logs -n ai-agents -l app=architect-agent
kubectl logs -n ai-agents -l app=coder-agent
kubectl logs -n ai-agents -l app=tester-agent

# 外部環境のログ
kubectl logs -n external-env -l app=mysql
kubectl logs -n external-env -l app=redis
kubectl logs -n external-env -l app=php-app
kubectl logs -n external-env -l app=nginx
```

## 📝 開発者向け情報

### エージェント追加方法

1. `agents/new-agent/` ディレクトリを作成
2. `logic.py` と `Dockerfile` を実装
3. `k8s/ai-agents/new-agent.yaml` マニフェストを作成
4. `manage-k8s.sh` にビルドコマンドを追加

### 外部サービス追加方法

1. `k8s/external-env/new-service.yaml` マニフェストを作成
2. `agents/common/external_env_client.py` にクライアント実装を追加
3. 必要に応じて環境変数を各エージェントに追加

## 🔐 セキュリティ

- エージェント間通信はKubernetes内部ネットワークで実行
- 外部環境は専用ネームスペースで分離
- 機密情報は環境変数またはKubernetes Secretsで管理

## 📄 ライセンス

MIT License
