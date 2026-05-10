# ジョブ管理スクリプトガイド

パイプライン（日次/週次/カスタム）のジョブ状態を操作するためのスクリプト群のインターフェース仕様。

## スクリプト一覧

| スクリプト | パス | 役割 |
|---|---|---|
| create-jobs.py | `python3.12 ~/scripts/create-jobs.py` | 汎用ジョブファイル生成 |
| find-job.py | `python3.12 ~/scripts/find-job.py` | ジョブ検索・取得 |
| update-job.py | `python3.12 ~/scripts/update-job.py` | ジョブステータス更新 |

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
  {"job_name": "agent-b", "timeout": 600, "retry_delay": 60, "depends_on": "agent-a"}
]
```

### 使用例

```bash
# ファイル指定（推奨）
python3.12 ~/scripts/create-jobs.py --pipeline my_pipeline --base-date 2026-05-10 \
  --jobs-file ~/jobs-def.json

# インライン指定
python3.12 ~/scripts/create-jobs.py --pipeline my_pipeline --base-date 2026-05-10 \
  --jobs '[{"job_name":"agent-a","timeout":300,"retry_delay":30,"depends_on":null}]'
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
| `--job-id` | - | - | 特定のjob_idで検索 |
| `--job-name` | - | - | 特定のjob_nameで検索 |
| `--scope` | - | `child` | `parent`: 親ジョブのみ / `child`: 子ジョブのみ |
| `--limit` | - | `1` | 返す件数の上限 |

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
  "jobs": [ { "job_id": "...", "job_name": "...", "status": "...", ... } ],
  "parent": { "job_id": "...", "job_name": "...", "status": "...", ... }
}
```

### 使用例

```bash
# startingの子ジョブを1件取得
python3.12 ~/scripts/find-job.py --pipeline daily --status starting --limit 1

# 親ジョブの状態確認
python3.12 ~/scripts/find-job.py --pipeline daily --scope parent

# 特定ジョブの状態確認
python3.12 ~/scripts/find-job.py --pipeline weekly --job-name slack-digest-scout

# 全failedジョブを取得
python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 10
```

## update-job.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--job-file` | ✅ | - | 対象ジョブファイルのパス |
| `--job-id` | scope=child時 | - | 更新対象の子ジョブID |
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

## 手動リカバリ手順

### 失敗ジョブのリトライ

```bash
# 1. 失敗ジョブを確認
python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 10

# 2. 対象ジョブをstartingに戻す
JOB_FILE=$(python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 1 | jq -r '.job_file')
JOB_ID=$(python3.12 ~/scripts/find-job.py --pipeline daily --status failed --limit 1 | jq -r '.jobs[0].job_id')
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --job-id "$JOB_ID" \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'

# 3. 親ジョブもrunningに戻す（completedやfailedになっている場合）
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --scope parent \
  --set '{"status": "running", "status_detail": "リトライ中"}'
```

### パイプライン全体のリセット

```bash
# 全子ジョブをstartingに戻す（注意: 全ジョブが再実行される）
JOB_FILE=$(python3.12 ~/scripts/find-job.py --pipeline daily --scope parent | jq -r '.job_file')
for JOB_ID in $(jq -r '.child_jobs[].job_id' "$JOB_FILE"); do
  python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --job-id "$JOB_ID" \
    --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
done
python3.12 ~/scripts/update-job.py --job-file "$JOB_FILE" --scope parent \
  --set '{"status": "running", "status_detail": null, "completed_at": null, "error": null}'
```

## 設計思想

- **抽象レイヤー**: Watcherはスクリプトのインターフェース（引数と出力JSON）のみに依存する
- **バックエンド非依存**: 内部実装をDB/APIに差し替えても、出力形式を維持すればWatcher変更不要
- **循環発火防止**: `executeBash` 経由のため postToolUse(write) が発火しない
- **アトミック書き込み**: `mktemp` + `mv` パターンで中間状態を防止
- **自動updated_at**: `--set` に `updated_at` を含めなければ現在時刻が自動付与される
