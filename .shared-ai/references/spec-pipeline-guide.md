# 仕様駆動開発パイプラインガイド

仕様駆動開発（SDD）時のマルチエージェント構成での開発ワークフロー。各エージェントの役割、切り替えタイミング、情報引き継ぎ方法を定義する。

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

## タスクファイルによる進捗管理

scoutパイプラインと同じタスクファイル形式で進捗を管理する。
テンプレート: `~/.shared-ai/templates/job-file.json`

### タスクファイルの配置

```
Documents/works/jobs/spec/{TASK_ID}_spec.json
```

### specパイプラインのタスクファイル例

```json
{
  "job_id": "{ULID}",
  "job_name": "spec_pipeline",
  "args": {
    "spec_path": ".kiro/specs/{feature-name}/",
    "spec_type": "feat"
  },
  "options": {
    "async": false,
    "timeout_seconds": 7200,
    "max_retries": 0,
    "retry_delay_seconds": 0
  },
  "status": "pending",
  "status_detail": null,
  "depends_on": null,
  "child_jobs": [
    {
      "job_id": "{ULID}",
      "job_name": "investigator",
      "args": { "spec_path": ".kiro/specs/{feature-name}/" },
      "options": { "async": true, "timeout_seconds": 600, "max_retries": 0, "retry_delay_seconds": 0 },
      "status": "starting",
      "status_detail": null,
      "depends_on": null,
      "child_jobs": [],
      "created_at": "{ISO8601}",
      "updated_at": "{ISO8601}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "job_id": "{ULID}",
      "job_name": "spec-architect",
      "args": { "spec_path": ".kiro/specs/{feature-name}/" },
      "options": { "async": true, "timeout_seconds": 900, "max_retries": 0, "retry_delay_seconds": 0 },
      "status": "pending",
      "status_detail": null,
      "depends_on": ["investigator"],
      "child_jobs": [],
      "created_at": "{ISO8601}",
      "updated_at": "{ISO8601}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "job_id": "{ULID}",
      "job_name": "implementer",
      "args": { "spec_path": ".kiro/specs/{feature-name}/" },
      "options": { "async": true, "timeout_seconds": 3600, "max_retries": 0, "retry_delay_seconds": 0 },
      "status": "pending",
      "status_detail": null,
      "depends_on": ["spec-architect"],
      "child_jobs": [],
      "created_at": "{ISO8601}",
      "updated_at": "{ISO8601}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "job_id": "{ULID}",
      "job_name": "integration-tester",
      "args": { "spec_path": ".kiro/specs/{feature-name}/" },
      "options": { "async": true, "timeout_seconds": 1800, "max_retries": 0, "retry_delay_seconds": 0 },
      "status": "pending",
      "status_detail": null,
      "depends_on": ["implementer"],
      "child_jobs": [],
      "created_at": "{ISO8601}",
      "updated_at": "{ISO8601}",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    {
      "job_id": "{ULID}",
      "job_name": "code-reviewer",
      "args": { "spec_path": ".kiro/specs/{feature-name}/" },
      "options": { "async": true, "timeout_seconds": 900, "max_retries": 0, "retry_delay_seconds": 0 },
      "status": "pending",
      "status_detail": null,
      "depends_on": ["integration-tester"],
      "child_jobs": [],
      "created_at": "{ISO8601}",
      "updated_at": "{ISO8601}",
      "started_at": null,
      "completed_at": null,
      "error": null
    }
  ],
  "created_at": "{ISO8601}",
  "updated_at": "{ISO8601}",
  "started_at": null,
  "completed_at": null,
  "error": null
}
```

### scoutパイプラインとの違い

| 観点 | scout | spec |
|---|---|---|
| 子タスクの実行順序 | 並列（`depends_on: null`） | 直列（`depends_on: ["{前のエージェント}"]`） |
| 子タスクの `status` 初期値 | 全て `starting` | 最初のみ `starting`、残りは `pending` |
| 親タスクの `args` | `base_date` | `spec_path`, `spec_type` |
| ジョブ管理スクリプト | `find-job.py --pipeline daily\|weekly` | 将来対応（現時点は手動管理） |

### ステータス遷移

```
pending → starting → running → completed / failed
```

- `pending`: 前のエージェントが完了するまで待機（`depends_on` が指定されている場合）
- `starting`: 実行準備完了（次に実行される）
- `running`: 実行中
- `completed`: 正常完了
- `failed`: エラー終了

### 進捗更新の責務

各エージェントは自分の子タスクのステータスを更新する:
1. 実行開始時: `status: "running"`, `started_at: "{現在時刻}"`
2. 正常完了時: `status: "completed"`, `completed_at: "{現在時刻}"`
3. エラー時: `status: "failed"`, `error: "{エラー内容}"`
4. 次エージェントの `status` を `"starting"` に更新（`depends_on` が自分の場合）

## 実行方式

### IDE方式（手動切り替え）

ユーザーがエージェントを手動で切り替える。steering `spec-pipeline.md`（fileMatch: `Documents/works/jobs/spec/**/*.json`）がタスクファイル操作時に自動注入され、次のエージェントへの切り替えを提案する。

### kiro-cli方式（自動実行）

```bash
# 各エージェントを順次実行
kiro-cli chat --trust-all-tools --no-interactive \
  "{agent-name} エージェントとして動作してください。~/.shared-ai/prompts/{agent-name}.md をreadFileで読み込み、ワークフローに従って実行してください。対象spec: {spec_path}"
```

## 各エージェントの完了条件

| エージェント | 完了条件 | 次エージェントへの引き継ぎ |
|---|---|---|
| investigator | 調査結果を `docs/domain/` に記録完了 | spec-architectに「調査完了、方針検討をお願いします」と報告 |
| spec-architect | requirements.md + design.md + tasks.md 作成完了、ユーザー承認済み | implementerに「tasks.mdに沿って実装を開始してください」と報告 |
| implementer | tasks.mdの全チェックボックスが `[x]` | integration-testerまたはcode-reviewerに「実装完了、検証をお願いします」と報告 |
| integration-tester | 全テストケースPASS、検証結果報告完了 | code-reviewerに「検証完了、PR作成をお願いします」と報告 |
| code-reviewer | 品質チェックPASS、PR作成完了 | ユーザーに「PR作成完了」と報告 |
