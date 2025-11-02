# PlannerAgent 再帰的開発サイクル指示書

## 📋 概要

PlannerAgentが開発完了報告を受けた後、自動的に次の開発タスクを検討・計画し、継続的な開発サイクルを実現するためのシステム仕様。

## 🔄 再帰的開発サイクルフロー

### 1. 完了報告受信フェーズ
```
TesterAgent → PlannerAgent: 開発完了報告
├── 実装済み機能リスト
├── テスト結果サマリー
├── 品質メトリクス
└── 発見された課題・改善点
```

### 2. 次期開発検討フェーズ
PlannerAgentは以下の優先順位で次期開発を検討：

#### 優先度1: 緊急対応
- セキュリティ脆弱性の修正
- 重大なバグの修正
- パフォーマンス問題の解決

#### 優先度2: 品質改善
- テストカバレッジ向上
- コードリファクタリング
- ドキュメント整備

#### 優先度3: 機能拡張
- 新機能の追加
- 既存機能の改善
- ユーザビリティ向上

#### 優先度4: 技術的改善
- 依存関係の更新
- アーキテクチャの最適化
- 開発環境の改善

### 3. 開発計画策定フェーズ
```
PlannerAgent内部処理:
├── 現在の開発状況分析
├── リソース可用性確認
├── 技術的制約の評価
├── 開発優先度の決定
└── 次期開発計画の策定
```

### 4. 開発指示発行フェーズ
```
PlannerAgent → ArchitectAgent: 次期開発指示
├── 開発目標
├── 技術要件
├── 品質基準
└── 完了条件
```

## 🤖 PlannerAgent拡張仕様

### 新規追加メソッド

#### `analyze_completion_report(report: CompletionReport) -> AnalysisResult`
完了報告を分析し、次期開発の候補を抽出

#### `prioritize_next_tasks(candidates: List[TaskCandidate]) -> List[PrioritizedTask]`
開発候補を優先度順にソート

#### `generate_development_plan(tasks: List[PrioritizedTask]) -> DevelopmentPlan`
次期開発計画を策定

#### `issue_next_development_instruction(plan: DevelopmentPlan) -> None`
ArchitectAgentに次期開発を指示

### 状態管理

#### `DevelopmentState`
```python
class DevelopmentState:
    current_cycle: int
    completed_features: List[Feature]
    pending_issues: List[Issue]
    quality_metrics: QualityMetrics
    resource_status: ResourceStatus
```

#### `CompletionReport`
```python
class CompletionReport:
    cycle_id: str
    completed_tasks: List[Task]
    test_results: TestResults
    quality_score: float
    discovered_issues: List[Issue]
    recommendations: List[Recommendation]
```

## 📊 意思決定ロジック

### 次期開発決定アルゴリズム

1. **緊急度評価**
   - セキュリティスコア < 7.0 → 緊急対応
   - バグ重要度 = Critical → 緊急対応

2. **品質評価**
   - テストカバレッジ < 90% → 品質改善
   - 技術的負債スコア > 6.0 → リファクタリング

3. **機能評価**
   - ユーザーフィードバック分析
   - 市場要求分析
   - 競合分析

4. **リソース評価**
   - 開発チーム負荷
   - インフラリソース
   - 予算制約

### 開発停止条件

以下の条件で再帰的サイクルを一時停止：
- 重大なセキュリティ問題発生
- システムリソース不足
- 外部依存サービス障害
- 手動停止指示受信

## 🔧 設定可能パラメータ

### `planner_config.yaml`
```yaml
recursive_cycle:
  enabled: true
  max_cycles: 100
  cycle_interval_minutes: 30
  
quality_thresholds:
  min_test_coverage: 90
  max_technical_debt_score: 6.0
  min_security_score: 7.0
  
priority_weights:
  security: 1.0
  bugs: 0.8
  quality: 0.6
  features: 0.4
  
resource_limits:
  max_concurrent_tasks: 3
  max_memory_usage_mb: 2048
  max_cpu_usage_percent: 80
```

## 📝 ログ・監視

### 必須ログ出力
- サイクル開始/完了時刻
- 意思決定プロセス詳細
- リソース使用状況
- エラー・警告情報

### 監視メトリクス
- サイクル実行回数
- 平均サイクル時間
- 成功/失敗率
- リソース使用率

## 🚨 エラーハンドリング

### 例外処理
- ArchitectAgent応答タイムアウト
- リソース不足エラー
- 外部サービス接続エラー
- 設定ファイル読み込みエラー

### 復旧処理
- 自動リトライ機能
- フォールバック処理
- 手動介入通知
- 緊急停止機能

## 🔄 実装フェーズ

### Phase 1: 基本サイクル実装
- 完了報告受信機能
- 基本的な次期開発決定ロジック
- ArchitectAgentへの指示発行

### Phase 2: 高度な分析機能
- 品質メトリクス分析
- 技術的負債評価
- セキュリティ分析

### Phase 3: 学習・最適化機能
- 過去の開発履歴学習
- 意思決定精度向上
- 動的パラメータ調整
