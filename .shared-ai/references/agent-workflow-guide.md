# エージェントワークフローガイド

マルチエージェント構成での開発ワークフロー。各エージェントの役割、切り替えタイミング、情報引き継ぎ方法を定義する。

## エージェント一覧

| エージェント       | 役割        | 主な成果物                           |
| ------------------ | ----------- | ------------------------------------ |
| investigator       | 調査        | 調査結果（docs/domain/更新）         |
| spec-architect     | 方針検討    | requirements.md; design.md; tasks.md |
| implementer        | 実装+テスト | ソースコード; ユニット/機能テスト    |
| integration-tester | 結合テスト  | E2Eテスト; 検証結果レポート          |
| code-reviewer      | レビュー+PR | レビュー結果; PR                     |

## 標準ワークフロー

### 新機能開発

```
investigator → spec-architect → implementer → integration-tester → code-reviewer
```

1. investigator: ドメイン知識の調査、DB構造の確認、影響範囲の特定
2. spec-architect: requirements.md → design.md → tasks.md の作成
3. implementer: tasks.mdに沿った実装とユニット/機能テスト
4. integration-tester: E2Eテスト、検証環境での確認
5. code-reviewer: 品質チェック、specとの整合性確認、PR作成

### 不具合修正

```
investigator → spec-architect → implementer → code-reviewer
```

1. investigator: 不具合の再現確認、根本原因の特定、DB状態の確認
2. spec-architect: fix specの作成（再現手順、根本原因、修正方針）
3. implementer: 修正実装 + 再現テスト + リグレッションテスト
4. code-reviewer: 品質チェック、PR作成

### 調査・検討のみ

```
investigator → (spec-architect)
```

1. investigator: ドメイン知識の調査、DB調査
2. spec-architect: 必要に応じてspecを作成（調査結果を元に）

## エージェント切り替えのタイミング

| 切り替え元         | 切り替え先         | トリガー                                          |
| ------------------ | ------------------ | ------------------------------------------------- |
| investigator       | spec-architect     | 調査完了、方針検討が必要                          |
| spec-architect     | implementer        | tasks.md作成完了、ユーザー承認済み                |
| implementer        | integration-tester | 全タスク完了（tasks.mdの全チェックボックスが[x]） |
| implementer        | code-reviewer      | 結合テスト不要の場合、全タスク完了後              |
| integration-tester | code-reviewer      | 結合テスト完了                                    |
| code-reviewer      | implementer        | レビュー指摘があり修正が必要                      |

## エージェント間の情報引き継ぎ

エージェント間の情報引き継ぎは、以下のファイルを介して行う:

| 引き継ぎ情報 | 格納場所                       | 書き込み者                  | 読み取り者                                     |
| ------------ | ------------------------------ | --------------------------- | ---------------------------------------------- |
| 調査結果     | docs/domain/                   | investigator                | spec-architect; implementer                    |
| 要件定義     | .kiro/specs/\*/requirements.md | spec-architect              | implementer; integration-tester; code-reviewer |
| 設計書       | .kiro/specs/\*/design.md       | spec-architect              | implementer; code-reviewer                     |
| タスクリスト | .kiro/specs/\*/tasks.md        | spec-architect; implementer | implementer; code-reviewer                     |
| テスト結果   | screenshots/; テスト出力       | integration-tester          | code-reviewer                                  |
| レビュー結果 | PR本文; コメント               | code-reviewer               | implementer                                    |

## 追加タスクの発生時

implementerが実装中に追加タスクを発見した場合:

1. tasks.mdに `A{連番}` IDで追加タスクを記録
2. タスク変更ログに発見フェーズと詳細理由を記録
3. 追加タスクの対応要件（REQ-N）を明記
4. 追加タスクが要件の範囲外の場合は、ユーザーに確認してから実施

## 差し戻しフロー

code-reviewerがレビュー指摘を出した場合:

1. code-reviewer: レビュー結果を報告（指摘内容、重要度）
2. ユーザー: 修正要否を判断
3. implementer: 修正実装（追加タスクとして記録）
4. code-reviewer: 再レビュー
