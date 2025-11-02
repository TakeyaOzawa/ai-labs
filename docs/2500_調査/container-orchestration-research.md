# コンテナオーケストレーション技術調査結果

## 調査概要

**調査日**: 2025-10-31  
**調査目的**: 開発環境コンテナから検証環境コンテナ群へのアクセス実現  
**要件**:
- 開発環境(PHP等)から検証環境(PHP, MySQL, Redis等)へのアクセス
- ARM64環境対応
- AWS CDK対応
- コスト効率性

## 技術選択肢の比較

### 1. Docker in Docker (DinD)

#### 構成例
```yaml
version: '3.8'
services:
  dind:
    image: docker:dind
    privileged: true
    environment:
      - DOCKER_TLS_CERTDIR=/certs
    volumes:
      - docker-certs-ca:/certs/ca
      - docker-certs-client:/certs/client
    ports:
      - "2376:2376"
    
  app:
    image: docker:cli
    depends_on:
      - dind
    environment:
      - DOCKER_HOST=tcp://dind:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    volumes:
      - docker-certs-client:/certs/client:ro
      - .:/workspace
    working_dir: /workspace

volumes:
  docker-certs-ca:
  docker-certs-client:
```

#### セキュリティリスク
- **Docker Socket共有**: ホストのDockerデーモンへの完全アクセス
- **Privileged権限**: ホストカーネルへの完全アクセス
- **コンテナエスケープ**: ネストされたコンテナからホストシステムへの侵入可能性

#### 対策
- Docker-in-Dockerの使用（Docker Socket共有を避ける）
- ネットワーク分離（internal: true）
- リソース制限の設定
- 最小権限の原則適用

### 2. Docker Swarm

#### メリット
- シンプルな学習コスト
- 軽量なオーバーヘッド

#### デメリット
- AWS統合が限定的
- ARM対応が不完全
- 将来性に不安（Dockerの戦略変更）

### 3. Kubernetes

#### メリット
- AWS CDK完全対応
- ARM64ネイティブサポート
- 豊富なAWSサービス統合
- 優れたスケーラビリティ
- 豊富なエコシステム

#### デメリット
- 学習コストが高い
- 初期セットアップの複雑さ

## 推奨ソリューション

### AWS環境: Kubernetes (EKS)

#### AWS CDK構成例
```typescript
import * as eks from 'aws-cdk-lib/aws-eks';
import * as ec2 from 'aws-cdk-lib/aws-ec2';

export class DevEnvironmentStack extends Stack {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    const vpc = new ec2.Vpc(this, 'DevVpc', {
      maxAzs: 2
    });

    const cluster = new eks.Cluster(this, 'DevCluster', {
      vpc,
      version: eks.KubernetesVersion.V1_28,
      defaultCapacity: 0
    });

    // ARM64ノードグループ
    cluster.addNodegroupCapacity('arm64-nodes', {
      instanceTypes: [ec2.InstanceType.of(
        ec2.InstanceClass.M6G, 
        ec2.InstanceSize.MEDIUM
      )],
      minSize: 1,
      maxSize: 3
    });
  }
}
```

#### 料金最適化
- **EKSコントロールプレーン**: $0.10/時間 ($73/月)
- **Spot Instances活用**: 最大90%のコスト削減
- **Fargate活用**: サーバーレス実行
- **Gravitonインスタンス**: 30-40%のコスト削減

### ローカル環境: k3s (推奨)

#### セットアップ
```bash
# k3sインストール (ARM64対応)
curl -sfL https://get.k3s.io | sh -

# kubectlエイリアス設定
echo 'alias kubectl="sudo k3s kubectl"' >> ~/.bashrc
source ~/.bashrc
```

#### 開発環境構成
```yaml
# dev-environment.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dev
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: php-dev
  namespace: dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: php-dev
  template:
    metadata:
      labels:
        app: php-dev
    spec:
      containers:
      - name: php
        image: php:8.2-fpm-alpine
        ports:
        - containerPort: 9000
        volumeMounts:
        - name: code
          mountPath: /var/www/html
      volumes:
      - name: code
        hostPath:
          path: /home/user/project
```

#### 検証環境構成
```yaml
# test-stack.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-stack
  namespace: test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-stack
  template:
    metadata:
      labels:
        app: test-stack
    spec:
      containers:
      - name: php
        image: php:8.2-fpm-alpine
        ports:
        - containerPort: 9000
      - name: mysql
        image: mysql:8.0
        env:
        - name: MYSQL_ROOT_PASSWORD
          value: "password"
        ports:
        - containerPort: 3306
      - name: redis
        image: redis:alpine
        ports:
        - containerPort: 6379
```

## ローカルKubernetes選択肢比較

| ソリューション | メモリ使用量 | CPU使用量 | 起動時間 | ARM64対応 | 推奨度 |
|---------------|-------------|-----------|----------|-----------|--------|
| **k3s**       | ~200MB      | 低        | ~30秒    | ✅ 最適化  | ⭐⭐⭐⭐⭐ |
| minikube      | ~500MB      | 中        | ~60秒    | ✅ 対応   | ⭐⭐⭐   |
| kind          | ~300MB      | 中        | ~45秒    | ✅ 対応   | ⭐⭐⭐⭐ |

## ARM64環境での注意点

### マルチアーキテクチャイメージ使用
```dockerfile
FROM --platform=$BUILDPLATFORM php:8.2-fpm-alpine
RUN apk add --no-cache mysql-client redis-tools
```

### イメージ確認
```bash
# ARM64対応イメージを使用
docker pull --platform linux/arm64 php:8.2-fpm-alpine
```

## 段階的移行プラン

### Phase 1: ローカル開発
- **現状**: Docker Compose
- **移行先**: k3s (ローカルKubernetes)
- **期間**: 1-2週間

### Phase 2: クラウド移行準備
- **AWS CDK**: EKS構成の準備
- **CI/CD**: パイプライン構築
- **期間**: 2-4週間

### Phase 3: 本格運用
- **EKS**: 本番環境デプロイ
- **監視**: CloudWatch統合
- **期間**: 1-2週間

## 最終推奨事項

### ローカル環境
**k3s** を採用
- ARM64最適化済み
- 最軽量 (200MB)
- 本番環境と同じ
- 完全無料

### AWS環境
**Kubernetes (EKS)** を採用
- AWS CDK完全対応
- ARM64 Gravitonサポート
- 豊富なAWSサービス統合
- 業界標準の将来性

### セキュリティ
- Docker in Dockerは避ける
- 最小権限の原則を適用
- ネットワーク分離を実装
- 継続的なセキュリティ監視

## 管理スクリプト例

```bash
#!/bin/bash
# manage.sh - 簡単な環境管理

case $1 in
  "start")
    kubectl apply -f dev-environment.yaml
    kubectl apply -f test-stack.yaml
    echo "環境を起動しました"
    ;;
  "stop")
    kubectl delete -f dev-environment.yaml
    kubectl delete -f test-stack.yaml
    echo "環境を停止しました"
    ;;
  "status")
    kubectl get pods -A
    ;;
  "logs")
    kubectl logs -n $2 -l app=$3 -f
    ;;
  *)
    echo "使用方法: $0 {start|stop|status|logs <namespace> <app>}"
    ;;
esac
```

## 結論

要件を満たす最適解は**Kubernetes**です。ローカル開発では**k3s**、AWS環境では**EKS**を採用することで、一貫した環境でありながらコスト効率とセキュリティを両立できます。

Docker in Dockerは技術的に可能ですが、セキュリティリスクが高いため推奨しません。Kubernetesエコシステムを活用することで、将来的な拡張性と保守性を確保できます。
