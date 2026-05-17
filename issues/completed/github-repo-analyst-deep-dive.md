# github-repo-analyst-consolidation: サブエージェント統合とdeepdive追加

## 変更種別

refactor / feat

## 概要

- `github-repo-analyst` のサブエージェントを5つ → 3つに統合
- current + history + future → `github-repo-analyst-github.md`（GitHub API統合版）
- web → 既存維持
- deepdive → テスト戦略Stepを追加

## 問題・背景

- 旧構成（current, history, future）はデータソースが同じ（GitHub API）で、相互参照できないため断片的な分析になっていた
- コントリビューター情報とPR作成者を突き合わせる等、統合することで一貫した分析が可能に
- サブエージェント呼び出しのオーバーヘッド削減（5回 → 3回）
- 一時ファイル管理の簡素化（5ファイル → 3ファイル）

## 修正対象

- `.shared-ai/prompts/github-repo-analyst.md`（親エージェント: 全面書き換え）
- `.shared-ai/prompts/github-repo-analyst-github.md`（新規: 統合版）
- `.shared-ai/prompts/github-repo-analyst-deepdive.md`（更新: テスト戦略Step追加）
- `.shared-ai/prompts/github-repo-analyst-current.md`（削除）
- `.shared-ai/prompts/github-repo-analyst-history.md`（削除）
- `.shared-ai/prompts/github-repo-analyst-future.md`（削除）

## タスク分解

### Task 1: 統合版サブエージェント作成

- **対象ファイル:** `.shared-ai/prompts/github-repo-analyst-github.md`
- **変更内容:** current + history + future の全Stepを統合。API呼び出し上限30回。セキュリティ（Dependabotアラート）追加。

### Task 2: deepdiveにテスト戦略Step追加

- **対象ファイル:** `.shared-ai/prompts/github-repo-analyst-deepdive.md`
- **変更内容:** Step 9にテスト戦略の詳細分析を追加。出力テンプレートにテスト戦略セクション追加。

### Task 3: 親エージェント更新

- **対象ファイル:** `.shared-ai/prompts/github-repo-analyst.md`
- **変更内容:** 5サブエージェント → 3サブエージェント。レポート構成にテスト戦略・メンテナンス健全性セクション追加。

### Task 4: 旧ファイル削除

- **対象ファイル:** current.md, history.md, future.md
- **変更内容:** 削除

## 影響範囲

- 次回以降の `github-repo-analyst` 実行時に新構成が適用される
- 既存の生成済みレポートには影響なし
- webサブエージェントには変更なし

## テスト計画

- [x] 新しいサブエージェントプロンプトが正しいMarkdown構文であること
- [x] 親エージェントプロンプトの整合性（サブエージェント数、ファイル名、レポート構成）
- [x] 旧ファイルが削除されていること
- [ ] 実際のリポジトリで実行して結果を確認（別途）
