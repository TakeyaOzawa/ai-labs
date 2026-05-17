# job-management-nested-hierarchy: ジョブ管理の三階層以上対応

## 変更種別

feat

## 概要

`create-jobs.py` / `create-*-jobs.py` / `update-job.py` を三階層以上のネスト構造に対応させる。現在は parent → child_jobs の二階層のみだが、サブパイプライン（例: `run-gws-trend-scout-pipeline.py`）の内部ステップも子ジョブとして追跡可能にする。

## 問題・背景

- **現状**: `run-daily-pipeline.py` の `AGENTS` にはエージェント名とパイプラインスクリプト（`.py`）を混在指定できるようになった
- **問題**: サブパイプライン（例: `run-gws-trend-scout-pipeline.py`）が実行されると、その内部ステップ（Step 1〜4）の進捗がジョブファイルに記録されない
- **結果**: `find-job.py` で確認しても `run-gws-trend-scout-pipeline` は1つの child_job としてしか見えず、内部の docs/slides/sheets/forms 各 extractor の成否が追跡できない
- **理想**: parent → child（サブパイプライン）→ grandchild（各ステップ）のように、任意の深さでジョブツリーを構成・更新・検索できる

## 現在の構造（二階層）

```json
{
  "job_id": "parent-id",
  "job_name": "scout_daily",
  "child_jobs": [
    { "job_id": "child-1", "job_name": "tech-trend-scout", "child_jobs": [] },
    { "job_id": "child-2", "job_name": "run-gws-trend-scout-pipeline", "child_jobs": [] }
  ]
}
```

## 目標の構造（三階層以上）

```json
{
  "job_id": "parent-id",
  "job_name": "scout_daily",
  "child_jobs": [
    { "job_id": "child-1", "job_name": "tech-trend-scout", "child_jobs": [] },
    {
      "job_id": "child-2",
      "job_name": "run-gws-trend-scout-pipeline",
      "child_jobs": [
        { "job_id": "grandchild-1", "job_name": "gws-extractor-docs", "child_jobs": [] },
        { "job_id": "grandchild-2", "job_name": "gws-extractor-slides", "child_jobs": [] },
        { "job_id": "grandchild-3", "job_name": "gws-extractor-sheets", "child_jobs": [] },
        { "job_id": "grandchild-4", "job_name": "gws-extractor-forms", "child_jobs": [] },
        { "job_id": "grandchild-5", "job_name": "gws-extractor-pdf", "child_jobs": [] },
        { "job_id": "grandchild-6", "job_name": "markdown-reporter", "child_jobs": [] }
      ]
    }
  ]
}
```

## 修正対象

| ファイル | 変更内容 |
|---|---|
| `scripts/create-jobs.py` | `--jobs` のジョブ定義に `child_jobs` ネストを許可。再帰的にジョブツリーを生成 |
| `scripts/create-daily-jobs.py` | サブパイプラインエントリに `child_jobs` 定義を追加 |
| `scripts/create-weekly-jobs.py` | 同上（該当するサブパイプラインがあれば） |
| `scripts/update-job.py` | `--job-id` でツリー内の任意ノードを再帰検索・更新可能に |
| `scripts/find-job.py` | ネストされた子ジョブの再帰検索・表示に対応 |
| `scripts/_pipeline_common.py` | `get_child_job_id()` の再帰検索対応 + サブパイプライン実行時に親ジョブファイルのパスを渡す仕組み |
| `scripts/run-gws-trend-scout-pipeline.py` | ジョブファイル連携（親から渡されたジョブファイルに grandchild を登録・更新） |
| `~/.shared-ai/references/job-management-guide.md` | インターフェース仕様ドキュメントの更新（ネスト対応後の新オプション・出力形式・使用例） |

## タスク分解

### Task 1: create-jobs.py のネスト対応

- **対象ファイル:** `scripts/create-jobs.py`
- **変更内容:**
  - `--jobs` のジョブ定義で `child_jobs` フィールドを再帰的に処理
  - 各レベルで `job_id` を自動生成
  - 既存の二階層定義は後方互換を維持（`child_jobs` 未指定なら空配列）

### Task 2: update-job.py の深層ノード更新対応

- **対象ファイル:** `scripts/update-job.py`
- **変更内容:**
  - `--job-id` 指定時にジョブツリー全体を再帰検索して対象ノードを特定
  - `--scope child` のままで深層ノードも更新可能にする（IDがユニークなので階層指定不要）
  - 既存の `--scope parent` / `--scope child` の動作は変更なし

### Task 3: find-job.py のネスト表示対応

- **対象ファイル:** `scripts/find-job.py`
- **変更内容:**
  - ジョブツリーをインデント付きで表示
  - `--job-id` で深層ノードも検索可能に

### Task 4: create-*-jobs.py のサブパイプライン子ジョブ定義

- **対象ファイル:** `scripts/create-daily-jobs.py`, `scripts/create-weekly-jobs.py`
- **変更内容:**
  - サブパイプラインエントリ（例: `run-gws-trend-scout-pipeline`）に `child_jobs` を定義
  - GWSパイプラインの場合: docs, slides, sheets, forms, pdf の各 extractor + reporter

### Task 5: _pipeline_common.py のサブパイプライン連携

- **対象ファイル:** `scripts/_pipeline_common.py`
- **変更内容:**
  - `get_child_job_id()` を再帰検索に対応（ネストされた child_jobs 内も探索）
  - サブパイプライン実行時に `--job-file` と `--parent-job-id` を環境変数またはCLI引数で渡す
  - サブパイプライン側が受け取って grandchild ジョブの状態を更新する仕組み

### Task 6: run-gws-trend-scout-pipeline.py のジョブ連携実装

- **対象ファイル:** `scripts/run-gws-trend-scout-pipeline.py`
- **変更内容:**
  - 親パイプラインからジョブファイルパスと自身のjob_idを受け取る
  - 各ステップ実行時に `update-job.py` で grandchild ジョブを更新
  - 単独実行時（ジョブファイルなし）は従来通り動作（後方互換）

### Task 7: ジョブ管理ガイドのドキュメント更新

- **対象ファイル:** `~/.shared-ai/references/job-management-guide.md`
- **変更内容:**
  - `create-jobs.py` のジョブ定義形式に `child_jobs` ネストの説明を追加
  - `find-job.py` の再帰検索オプション・出力形式の更新
  - `update-job.py` の深層ノード更新の使用例を追加
  - 手動リカバリ手順のネスト対応版を追記

## 影響範囲

- 既存のジョブファイル形式は後方互換（`child_jobs` が空配列のノードは従来と同じ）
- `find-job.py` の出力フォーマットが変わる（ネスト表示追加）
- サブパイプラインの単独実行には影響なし（ジョブファイル未指定時はジョブ管理をスキップ）

## テスト計画

- [ ] `create-jobs.py` でネストされたジョブ定義からジョブファイルが正しく生成される
- [ ] `update-job.py` で grandchild ノードを `--job-id` 指定で更新できる
- [ ] `find-job.py` でネストされたジョブツリーが正しく表示される
- [ ] `run-daily-pipeline.py` 実行時にサブパイプラインの内部ステップが追跡される
- [ ] サブパイプライン単独実行時に従来通り動作する（後方互換）
- [ ] `job-management-guide.md` の使用例が実際のCLI動作と一致する
