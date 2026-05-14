# ジョブ管理スクリプトガイド

パイプライン（日次/週次/カスタム）のジョブ状態を操作するためのスクリプト群のインターフェース仕様。

## スクリプト一覧

| スクリプト | パス | 役割 |
|---|---|---|
| create-jobs.py | `python3.12 ~/scripts/create-jobs.py` | 汎用ジョブファイル生成 |
| find-job.py | `python3.12 ~/scripts/find-job.py` | ジョブ検索・取得 |
| update-job.py | `python3.12 ~/scripts/update-job.py` | ジョブステータス更新 |

## ジョブツリー構造

ジョブは任意の深さでネスト可能。典型的な三階層構造:

```
parent (scout_daily)
├── child (tech-trend-scout)
├── child (run-gws-trend-scout-pipeline)
│   ├── grandchild (gws-extractor-docs)
│   ├── grandchild (gws-extractor-slides)
│   ├── grandchild (gws-extractor-sheets)
│   ├── grandchild (gws-extractor-forms)
│   ├── grandchild (gws-extractor-pdf)
│   └── grandchild (markdown-reporter)
└── child (slack-trend-scout)
```

## create-jobs.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--pipeline` | ✅ | - | パイプライン名（出力ディレクトリ名） |
| `--base-date` | - | 昨日 | 基準日（YYYY-MM-DD） |
| `--jobs-file` | ※ | - | ジョブ定義JSONファイルのパス |
| `--jobs` | ※ | - | ジョブ定義のJSON文字列（インライン） |
| `--parent-timeout` | - | `3600` | 親ジョブのタイムアウト秒 |

※ `--jobs-file` または `--jobs` のいずれかが必須。

### ジョブ定義の形式

```json
[
  {"job_name": "agent-a", "timeout": 300, "retry_delay": 30, "depends_on": null},
  {
    "job_name": "sub-pipeline",
    "timeout": 900,
    "retry_delay": 60,
    "child_jobs": [
      {"job_name": "step-1", "timeout": 300, "retry_delay": 30},
      {"job_name": "step-2", "timeout": 300, "retry_delay": 30}
    ]
  }
]
```

`child_jobs` フィールドは再帰的に処理される。未指定の場合は空配列（後方互換）。

### depends_on フィールド

`depends_on` は依存先ジョブを指定するフィールド。以下の形式をサポート:

| 形式 | 例 | 説明 |
|------|-----|------|
| `null` | `"depends_on": null` | 依存なし（即時実行可能） |
| 配列 | `"depends_on": ["agent-a", "agent-b"]` | 依存あり（全完了後に実行可能） |

依存ありのジョブは初期ステータスが `pending` となり、パイプライン実行時に依存先が全て完了するまでスキップされる。

**注意:** 文字列形式（`"depends_on": "agent-a"`）は後方互換のため内部で配列に正規化されるが、新規定義では配列形式を使用すること。

### 使用例

```bash
# GitHub org トレンドスカウトパイプライン
python3.12 ~/scripts/create-jobs.py --pipeline github-org-trend-scout-pipeline --base-date 2026-05-14 \
  --jobs '[{"job_name":"github-org-repo-collector","timeout":300,"retry_delay":30,"depends_on":null},{"job_name":"github-org-pr-collector","timeout":600,"retry_delay":30,"depends_on":["github-org-repo-collector"]},{"job_name":"github-org-report-generator","timeout":300,"retry_delay":30,"depends_on":["github-org-pr-collector"]}]'

# ネストされたジョブ定義
python3.12 ~/scripts/create-jobs.py --pipeline scout_daily --base-date 2026-05-10 \
  --jobs '[{"job_name":"agent-a","timeout":300},{"job_name":"sub-pipe","timeout":900,"child_jobs":[{"job_name":"step-1","timeout":300}]}]'
```

### 出力

`~/Documents/works/jobs/{pipeline}/{base_date}_{job_id}_{pipeline}.json`

### ラッパースクリプト（後方互換）

| スクリプト | 委譲先 |
|---|---|
| `create-daily-jobs.py [基準日]` | `create-jobs.py --pipeline scout_daily` |
| `create-weekly-jobs.py [基準日]` | `create-jobs.py --pipeline scout_weekly` |

## find-job.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--pipeline` | ✅ | - | パイプライン名（`daily`, `weekly`, または任意のパイプライン名） |
| `--date` | - | 最新ファイル | 基準日（YYYY-MM-DD） |
| `--status` | - | - | フィルタするステータス |
| `--job-id` | - | - | 特定のjob_idで検索（ツリー全体を再帰検索） |
| `--job-name` | - | - | 特定のjob_nameで検索（ツリー全体を再帰検索） |
| `--scope` | - | `child` | `parent`: 親ジョブのみ / `child`: 子ジョブのみ |
| `--limit` | - | `1` | 返す件数の上限 |
| `--tree` | - | - | ジョブツリーをインデント付きで表示 |

### パイプライン名の解決

| 指定値 | 参照ディレクトリ |
|---|---|
| `daily` | `jobs/scout_daily/`（後方互換エイリアス） |
| `weekly` | `jobs/scout_weekly/`（後方互換エイリアス） |
| その他 | `jobs/{指定値}/` |

### ステータス値

`pending` / `starting` / `running` / `completed` / `failed`

### 出力形式

```json
{
  "found": true,
  "job_file": "/path/to/file.json",
  "jobs": [ { "job_id": "...", "job_name": "...", "status": "...", "child_jobs": [...] } ],
  "parent": { "job_id": "...", "job_name": "...", "status": "...", ... }
}
```

### --tree 出力例

```
✅ scout_daily [completed] id=019746a1b2c3...
  ✅ tech-trend-scout [completed] id=019746a1b2c4...
  ✅ run-gws-trend-scout-pipeline [completed] id=019746a1b2c5...
    ✅ gws-extractor-docs [completed] id=019746a1b2c6...
    ✅ gws-extractor-slides [completed] id=019746a1b2c7...
    ❌ gws-extractor-sheets [failed] id=019746a1b2c8... error=kiro-cli exit non-zero
    ✅ gws-extractor-forms [completed] id=019746a1b2c9...
    ✅ gws-extractor-pdf [completed] id=019746a1b2ca...
    ✅ markdown-reporter [completed] id=019746a1b2cb...
  🔄 slack-trend-scout [running] id=019746a1b2cc...
```

### 使用例

```bash
# ツリー表示
python3.12 ~/scripts/find-job.py --pipeline daily --tree

# grandchildジョブを名前で検索
python3.12 ~/scripts/find-job.py --pipeline daily --job-name gws-extractor-docs

# 全failedジョブを取得（第一階層のみ）
python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 10

# 親ジョブの状態確認
python3.12 ~/scripts/find-job.py --pipeline daily --scope parent
```

## update-job.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--job-file` | ✅ | - | 対象ジョブファイルのパス |
| `--job-id` | scope=child時 | - | 更新対象のジョブID（ツリー全体を再帰検索） |
| `--scope` | - | `child` | `parent`: 親ジョブを更新 / `child`: 子ジョブを更新 |
| `--set` | ✅ | - | 更新するフィールドのJSON |

### --set で指定可能なフィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | string | pending / starting / running / completed / failed |
| `status_detail` | string | 進捗メッセージ |
| `started_at` | string | ISO 8601 タイムスタンプ |
| `updated_at` | string | ISO 8601（省略時は自動付与） |
| `completed_at` | string | ISO 8601 タイムスタンプ |
| `error` | string | エラーメッセージ |

### 深層ノード更新

`--job-id` はジョブツリー全体を再帰検索する。grandchild以下のノードも直接IDを指定して更新可能。

```bash
# grandchildジョブを直接更新
python3.12 ~/scripts/update-job.py --job-file /path/to/file.json \
  --job-id 019746a1b2c6-abcd1234 \
  --set '{"status": "running", "started_at": "2026-05-10T10:00:00+09:00"}'
```

### 出力形式

```json
{
  "success": true,
  "job_file": "/path/to/file.json",
  "job_id": "...",
  "scope": "child",
  "before": { "status": "starting", ... },
  "after": { "status": "running", ... },
  "message": "Job xxx updated: starting → running"
}
```

### 使用例

```bash
# 子ジョブをrunningに
python3.12 ~/scripts/update-job.py --job-file /path/to/file.json \
  --job-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "running", "started_at": "2026-05-05T16:10:44+09:00"}'

# 親ジョブのstatus_detailを更新
python3.12 ~/scripts/update-job.py --job-file /path/to/file.json \
  --scope parent \
  --set '{"status_detail": "tech-trend-scout 実行中"}'

# 失敗したジョブをstartingに戻す（リトライ）
python3.12 ~/scripts/update-job.py --job-file /path/to/file.json \
  --job-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
```

## サブパイプライン連携

### 仕組み

親パイプライン（`_pipeline_common.py`）がサブパイプラインを実行する際、以下の環境変数を設定する:

| 環境変数 | 内容 |
|---|---|
| `PIPELINE_JOB_FILE` | ジョブファイルの絶対パス |
| `PIPELINE_PARENT_JOB_ID` | サブパイプライン自身のjob_id |

サブパイプライン側はこれらを読み込み、内部ステップ実行時に `update-job.py` でgrandchildジョブを更新する。

### 後方互換

環境変数が未設定の場合（単独実行時）、ジョブ管理はスキップされ従来通り動作する。

## 手動リカバリ手順

### 失敗ジョブのリトライ

```bash
# 1. 失敗ジョブを確認（ツリー表示で全体把握）
python3.12 ~/scripts/find-job.py --pipeline daily --tree

# 2. 対象ジョブをstartingに戻す（grandchildも直接指定可能）
JOB_FILE=$(python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 1 | jq -r '.job_file')
JOB_ID=$(python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 1 | jq -r '.jobs[0].job_id')
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --job-id "$JOB_ID" \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'

# 3. 親ジョブもrunningに戻す（completedやfailedになっている場合）
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --scope parent \
  --set '{"status": "running", "status_detail": "リトライ中"}'
```

### grandchildジョブのリトライ

```bash
# grandchildジョブを名前で検索してリセット
JOB_FILE=$(python3.12 ~/scripts/find-job.py --pipeline daily --scope parent | jq -r '.job_file')
GC_ID=$(python3.12 ~/scripts/find-job.py --pipeline daily --job-name gws-extractor-sheets | jq -r '.jobs[0].job_id')
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --job-id "$GC_ID" \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
```

### パイプライン全体のリセット

```bash
# 全子ジョブをstartingに戻す（注意: 全ジョブが再実行される）
JOB_FILE=$(python3.12 ~/scripts/find-job.py --pipeline daily --scope parent | jq -r '.job_file')
for JOB_ID in $(jq -r '.. | .job_id? // empty' "$JOB_FILE" | tail -n +2); do
  python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --job-id "$JOB_ID" \
    --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
done
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --scope parent \
  --set '{"status": "running", "status_detail": null, "completed_at": null, "error": null}'
```

## 設計思想

- **抽象レイヤー**: Watcherはスクリプトのインターフェース（引数と出力JSON）のみに依存する
- **バックエンド非依存**: 内部実装をDB/APIに差し替えても、出力形式を維持すればWatcher変更不要
- **再帰構造**: `child_jobs` は任意の深さでネスト可能。全検索・更新操作は再帰的に動作する
- **環境変数連携**: サブパイプラインへのジョブ情報伝達は環境変数経由（CLIインターフェースを汚さない）
- **後方互換**: ネスト未使用の既存ジョブファイルはそのまま動作する
- **循環発火防止**: `executeBash` 経由のため postToolUse(write) が発火しない
- **アトミック書き込み**: `mktemp` + `mv` パターンで中間状態を防止
- **自動updated_at**: `--set` に `updated_at` を含めなければ現在時刻が自動付与される
