# AI Development Multi-Agent System

マルチエージェントシステムによる自動開発プラットフォーム

## 📋 前提条件

### システム要件

#### 最小スペック
- **CPU**: 4コア以上（Intel/AMD x86_64 または Apple Silicon M1/M2）
- **メモリ**: 8GB RAM以上（推奨: 16GB以上）
- **ストレージ**: 50GB以上の空き容量（SSD推奨）
- **ネットワーク**: インターネット接続（Docker Hub、AWS、Slack、Notion API用）

#### 推奨スペック
- **CPU**: 8コア以上
- **メモリ**: 32GB RAM以上
- **ストレージ**: 100GB以上の空き容量（NVMe SSD）
- **ネットワーク**: 高速インターネット接続

### 必須ソフトウェア

#### Docker環境
- **Docker**: 24.0.0以上
- **Docker Compose**: 2.20.0以上
- **Docker Buildx**: マルチアーキテクチャビルド用

```bash
# インストール確認
docker --version          # Docker version 24.0.0以上
docker-compose --version  # Docker Compose version 2.20.0以上
docker buildx version     # buildx v0.11.0以上
```

#### Kubernetes環境（オプション）
- **kubectl**: 1.28.0以上
- **Kubernetes**: 1.28.0以上（Docker Desktop、minikube、またはクラウドプロバイダー）

```bash
# インストール確認
kubectl version --client  # Client Version: v1.28.0以上
```

#### システムツール
- **Git**: 2.30.0以上
- **curl**: 7.68.0以上
- **jq**: 1.6以上（JSON処理用）
- **make**: 4.2以上
- **bash**: 4.4以上

```bash
# インストール確認
git --version    # git version 2.30.0以上
curl --version   # curl 7.68.0以上
jq --version     # jq-1.6以上
make --version   # GNU Make 4.2以上
bash --version   # GNU bash, version 4.4以上
```

### 外部サービス

#### Amazon Web Services
- **AWSアカウント**: 有効なAWSアカウント
- **Amazon Q Developer**: 有効なインスタンス
- **AWS CLI**: 2.13.0以上（コンテナ内で自動インストール）
- **IAM権限**: S3、CloudWatch、Logs等の適切な権限

#### Slack（通知用）
- **Slackワークスペース**: 通知送信用
- **Slack App**: Bot Token取得用
- **Bot Token**: `xoxb-`で始まるOAuth Token
- **User ID**: 通知送信先のUser ID

#### Notion（ドキュメント管理用）
- **Notionワークスペース**: ドキュメント保存用
- **Notion Integration**: API Token取得用
- **Database**: 開発履歴保存用データベース

### プラットフォーム対応

#### サポート対象OS
- **Linux**: Ubuntu 20.04 LTS以上、CentOS 8以上、Amazon Linux 2
- **macOS**: macOS 12 (Monterey)以上（Intel/Apple Silicon両対応）
- **Windows**: Windows 11 + WSL2（Ubuntu 20.04以上）

#### アーキテクチャ対応
- **x86_64 (AMD64)**: Intel/AMD 64bit CPU
- **ARM64 (AArch64)**: Apple Silicon M1/M2、AWS Graviton

### ネットワーク要件

#### 必要ポート
- **8080**: PlannerAgent
- **8081**: ArchitectAgent  
- **8082**: CoderAgent
- **8083**: TesterAgent
- **3306**: MySQL
- **6379**: Redis
- **5432**: PostgreSQL
- **9090**: Prometheus（監視用）

#### 外部接続
- **Docker Hub**: `docker.io`, `registry-1.docker.io`
- **AWS Services**: `*.amazonaws.com`
- **Slack API**: `slack.com`, `api.slack.com`
- **Notion API**: `api.notion.com`
- **GitHub**: `github.com`（Amazon Q CLI取得用）

### インストール手順

#### 1. Dockerのインストール

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
```bash
# Docker Desktopをインストール
# https://docs.docker.com/desktop/install/mac-install/
```

**Windows:**
```bash
# Docker Desktop for Windowsをインストール
# https://docs.docker.com/desktop/install/windows-install/
# WSL2が必要
```

#### 2. 必須ツールのインストール

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y git curl jq make bash
```

**macOS:**
```bash
# Homebrewを使用
brew install git curl jq make bash
```

**Windows (WSL2):**
```bash
sudo apt update
sudo apt install -y git curl jq make bash
```

#### 3. Kubernetesのインストール（オプション）

**kubectl:**
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

**Docker Desktop Kubernetes:**
- Docker Desktop設定でKubernetesを有効化

### 動作確認

システム要件を満たしているか確認：

```bash
# システム情報
uname -a
cat /proc/cpuinfo | grep "processor" | wc -l  # CPU コア数
free -h                                        # メモリ容量
df -h                                         # ディスク容量

# Docker確認
docker --version
docker-compose --version
docker run hello-world

# 必須ツール確認
git --version && curl --version && jq --version && make --version
```

すべての確認が完了したら、[クイックスタート](#🚀-クイックスタート)に進んでください。

## 🏗️ システム構成

### AIエージェント
- **PlannerAgent** (Port: 8080) - タスク計画・指示・再帰的開発サイクル管理
- **ArchitectAgent** (Port: 8081) - システム設計
- **CoderAgent** (Port: 8082) - コード生成・修正
- **TesterAgent** (Port: 8083) - テスト実行・検証

### 状態管理・監視
- **Redis State Manager** (Port: 6380) - 開発サイクル状態管理
- **PostgreSQL History** (Port: 5433) - 開発履歴・品質メトリクス
- **Prometheus** (Port: 9090) - メトリクス収集・監視

### 外部開発環境
- **MySQL** (Port: 3306) - データベース
- **Redis** (Port: 6379) - キャッシュ
- **PHP-FPM** (Port: 9000) - アプリケーション実行
- **Nginx** (Port: 8090) - Webサーバー

### 外部連携
- **Amazon Q Developer** - AI開発支援
- **Slack** - 通知・進捗報告
- **Notion** - ドキュメント管理・開発履歴

## 🚀 クイックスタート

### 環境設定

1. 環境変数ファイルを作成：
```bash
cp .env.example .env
# .envファイルを編集して各種設定を行う
```

2. 主要な環境変数：

#### 基本設定
- `WORKSPACE_HOST_PATH`: ホストのワークスペースディレクトリパス
- `PLANNER_AGENT_PORT`: PlannerAgentのポート（デフォルト: 8080）
- `ARCHITECT_AGENT_PORT`: ArchitectAgentのポート（デフォルト: 8081）
- `CODER_AGENT_PORT`: CoderAgentのポート（デフォルト: 8082）
- `TESTER_AGENT_PORT`: TesterAgentのポート（デフォルト: 8083）

#### Amazon Q設定
- `AMAZON_Q_START_URL`: Amazon Q DeveloperのスタートURL
- `AMAZON_Q_REGION`: Amazon Qのリージョン（デフォルト: us-east-1）

#### Slack設定
- `AMAZON_Q_SLACK_OAUTH_TOKEN`: Slack Bot OAuth Token
- `AMAZON_Q_SLACK_USER_ID`: Slack User ID

#### Notion設定
- `NOTION_API_TOKEN`: Notion Integration Token
- `NOTION_DATABASE_ID`: Notion Database ID
- `NOTION_WORKSPACE_URL`: Notion Workspace URL

#### データベース設定
- `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

### Docker Composeを使用した起動

```bash
# 1. 環境変数を設定
cp .env.example .env
# .envファイルを編集

# 2. 全サービスを起動
docker-compose up -d

# 3. 状態確認
docker-compose ps

# 4. ログ確認
docker-compose logs -f planner-agent
```

### Kubernetesを使用した起動

```bash
# 1. 環境変数を設定
cp .env.example .env
# .envファイルを編集

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

### 3. Amazon Q Developerの起動

```bash
# Amazon Q Developerを起動
./scripts/start-amazon-q.sh
```

### 4. 外部環境の確認

```bash
# Nginx (Webサーバー)
curl http://localhost:8090/health

# MySQL接続テスト
mysql -h localhost -P 3306 -u testuser -ptestpass testdb -e "SELECT 1;"

# Redis接続テスト
redis-cli -h localhost -p 6379 ping
```

## 🔄 再帰的開発サイクル

PlannerAgentは開発完了報告を受けて自動的に次の開発タスクを計画・実行します：

### サイクルフロー
1. **完了報告受信** - TesterAgentからの開発完了報告
2. **次期開発検討** - 品質・セキュリティ・機能の優先度評価
3. **開発計画策定** - リソース制約を考慮した計画作成
4. **開発指示発行** - ArchitectAgentへの次期開発指示

### 優先度
1. セキュリティ脆弱性の修正
2. 重大なバグの修正
3. 品質改善（テストカバレッジ、リファクタリング）
4. 機能拡張・改善

## 🔧 管理コマンド

### 基本的な使用方法

```bash
# 初期セットアップ
make setup

# クイックスタート（セットアップ + ビルド + 起動）
make quick-start

# 個別コマンド
make build          # イメージビルド
make start          # サービス開始
make stop           # サービス停止
make status         # ステータス確認
make logs           # ログ表示
make destroy        # 完全削除
```

### 開発用コマンド

```bash
# 開発用クイックコマンド
./dev.sh quick-start     # セットアップ + ビルド + 起動
./dev.sh rebuild         # リビルド + 再起動
./dev.sh reset           # 完全リセット
./dev.sh debug           # デバッグシェル
./dev.sh monitor         # 開発監視

# 特定エージェントのテスト
./dev.sh test-agent planner-agent
```

### 監視・メトリクス

```bash
# システム監視
./scripts/monitor.sh status      # リソース使用状況
./scripts/monitor.sh health      # ヘルスチェック
./scripts/monitor.sh watch       # 継続監視
./scripts/monitor.sh alerts     # アラート確認

# Makefileでも利用可能
make monitor
make health
make watch
```

### バックアップ・復元

```bash
# バックアップ
./scripts/backup.sh full         # 完全バックアップ
./scripts/backup.sh config       # 設定のみ
./scripts/backup.sh data         # データベースのみ

# 復元
./scripts/backup.sh restore backups/backup_20231102_143022.tar.gz

# 管理
./scripts/backup.sh list         # バックアップ一覧
./scripts/backup.sh cleanup 7    # 7日以上古いバックアップ削除
```

### Kubernetes環境

```bash
# 全環境起動
./manage-k8s.sh start-all

# AIエージェントのみ起動
./manage-k8s.sh start-agents

# 外部開発環境のみ起動
./manage-k8s.sh start-external

# 監視スタック起動
./manage-k8s.sh start-monitoring

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
│   ├── planner-agent/        # PlannerAgent + 再帰的サイクル
│   ├── architect-agent/      # ArchitectAgent
│   ├── coder-agent/          # CoderAgent
│   └── tester-agent/         # TesterAgent
├── k8s/                      # Kubernetesマニフェスト
│   ├── ai-agents/           # AIエージェント用
│   ├── external-env/        # 外部開発環境用
│   └── monitoring/          # 監視スタック用
├── scripts/                 # 管理スクリプト
│   ├── start-amazon-q.sh   # Amazon Q起動
│   └── setup-k8s-env.sh    # Kubernetes環境設定
├── docs/                    # ドキュメント
├── project_root/            # 開発対象コードベース
├── .env.example            # 環境変数テンプレート
├── docker-compose.yml      # Docker Compose設定
├── manage-k8s.sh          # Kubernetes管理スクリプト
└── README.md              # このファイル
```

## 🔄 ワークフロー

1. **ユーザー** → **PlannerAgent**: 開発要求を送信
2. **PlannerAgent** → **ArchitectAgent**: 設計を依頼
3. **ArchitectAgent** → **CoderAgent**: コード生成を依頼
4. **CoderAgent** → **TesterAgent**: テスト実行を依頼
5. **TesterAgent** → **CoderAgent**: テスト結果を報告
6. **CoderAgent** → **PlannerAgent**: 完了報告
7. **PlannerAgent**: 次期開発サイクルを自動計画・実行

## 🔗 外部連携設定

### Amazon Q Developer設定
1. Amazon Q Developerのインスタンスを作成
2. `.env`ファイルに`AMAZON_Q_START_URL`を設定
3. `./scripts/start-amazon-q.sh`で起動
4. コンテナ起動時に`.amazonq`設定が自動生成される

### Slack設定
1. Slack Appを作成してBot Tokenを取得
2. `.env`ファイルに`AMAZON_Q_SLACK_OAUTH_TOKEN`と`AMAZON_Q_SLACK_USER_ID`を設定
3. 開発進捗が自動的にSlackに通知される

### Notion設定
1. Notion Integrationを作成してAPI Tokenを取得
2. データベースを作成してDatabase IDを取得
3. `.env`ファイルに設定
4. 開発サイクルの履歴がNotionに自動記録される

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

3. **環境変数設定エラー**
   ```bash
   # .envファイルの確認
   cat .env
   # 環境変数の読み込み確認
   docker-compose config
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

# 監視スタックのログ
kubectl logs -n monitoring -l app=prometheus
```

## 📊 監視・メトリクス

### Prometheus監視
- エージェント間通信の監視
- リソース使用率の追跡
- 開発サイクルのパフォーマンス測定

### 品質メトリクス
- テストカバレッジ
- 技術的負債スコア
- セキュリティスコア
- パフォーマンススコア

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
- Slack Token、Notion API Tokenは暗号化保存

## 📄 ライセンス

MIT License
