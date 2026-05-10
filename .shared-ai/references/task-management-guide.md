# タスク管理スクリプトガイド

scoutパイプライン（日次/週次）のタスク状態を操作するためのスクリプト群のインターフェース仕様。

## スクリプト一覧

| スクリプト | パス | 役割 |
|---|---|---|
| find-task.py | `python3.12 ~/scripts/find-task.py` | タスク検索・取得 |
| update-task.py | `python3.12 ~/scripts/update-task.py` | タスクステータス更新 |

## find-task.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--pipeline` | ✅ | - | `daily` または `weekly` |
| `--date` | - | 最新ファイル | 基準日（YYYY-MM-DD） |
| `--status` | - | - | フィルタするステータス |
| `--task-id` | - | - | 特定のtask_idで検索 |
| `--task-name` | - | - | 特定のtask_nameで検索 |
| `--scope` | - | `child` | `parent`: 親タスクのみ / `child`: 子タスクのみ |
| `--limit` | - | `1` | 返す件数の上限 |

### ステータス値

`pending` / `starting` / `running` / `completed` / `failed`

### 出力形式

```json
{
  "found": true,
  "task_file": "/path/to/file.json",
  "tasks": [ { "task_id": "...", "task_name": "...", "status": "...", ... } ],
  "parent": { "task_id": "...", "task_name": "...", "status": "...", ... }
}
```

### 使用例

```bash
# startingの子タスクを1件取得
python3.12 ~/scripts/find-task.py --pipeline daily --status starting --limit 1

# 親タスクの状態確認
python3.12 ~/scripts/find-task.py --pipeline daily --scope parent

# 特定タスクの状態確認
python3.12 ~/scripts/find-task.py --pipeline weekly --task-name slack-digest-scout

# 全failedタスクを取得
python3.12 ~/scripts/find-task.py --pipeline daily --status failed --limit 10
```

## update-task.py

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--task-file` | ✅ | - | 対象タスクファイルのパス |
| `--task-id` | scope=child時 | - | 更新対象の子タスクID |
| `--scope` | - | `child` | `parent`: 親タスクを更新 / `child`: 子タスクを更新 |
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
  "task_file": "/path/to/file.json",
  "task_id": "...",
  "scope": "child",
  "before": { "status": "starting", ... },
  "after": { "status": "running", ... },
  "message": "Task xxx updated: starting → running"
}
```

### 使用例

```bash
# 子タスクをrunningに
python3.12 ~/scripts/update-task.py --task-file /path/to/file.json \
  --task-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "running", "started_at": "2026-05-05T16:10:44+09:00"}'

# 親タスクのstatus_detailを更新
python3.12 ~/scripts/update-task.py --task-file /path/to/file.json \
  --scope parent \
  --set '{"status_detail": "tech-trend-scout 実行中"}'

# 失敗したタスクをstartingに戻す（リトライ）
python3.12 ~/scripts/update-task.py --task-file /path/to/file.json \
  --task-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
```

## 手動リカバリ手順

### 失敗タスクのリトライ

```bash
# 1. 失敗タスクを確認
python3.12 ~/scripts/find-task.py --pipeline daily --status failed --limit 10

# 2. 対象タスクをstartingに戻す
TASK_FILE=$(python3.12 ~/scripts/find-task.py --pipeline daily --status failed --limit 1 | jq -r '.task_file')
TASK_ID=$(python3.12 ~/scripts/find-task.py --pipeline daily --status failed --limit 1 | jq -r '.tasks[0].task_id')
python3.12 ~/scripts/update-task.py --task-file "$TASK_FILE" --task-id "$TASK_ID" \
  --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'

# 3. 親タスクもrunningに戻す（completedやfailedになっている場合）
python3.12 ~/scripts/update-task.py --task-file "$TASK_FILE" --scope parent \
  --set '{"status": "running", "status_detail": "リトライ中"}'
```

### パイプライン全体のリセット

```bash
# 全子タスクをstartingに戻す（注意: 全タスクが再実行される）
TASK_FILE=$(python3.12 ~/scripts/find-task.py --pipeline daily --scope parent | jq -r '.task_file')
for TASK_ID in $(jq -r '.child_tasks[].task_id' "$TASK_FILE"); do
  python3.12 ~/scripts/update-task.py --task-file "$TASK_FILE" --task-id "$TASK_ID" \
    --set '{"status": "starting", "error": null, "started_at": null, "completed_at": null}'
done
python3.12 ~/scripts/update-task.py --task-file "$TASK_FILE" --scope parent \
  --set '{"status": "running", "status_detail": null, "completed_at": null, "error": null}'
```

## 設計思想

- **抽象レイヤー**: Watcherはスクリプトのインターフェース（引数と出力JSON）のみに依存する
- **バックエンド非依存**: 内部実装をDB/APIに差し替えても、出力形式を維持すればWatcher変更不要
- **循環発火防止**: `executeBash` 経由のため postToolUse(write) が発火しない
- **アトミック書き込み**: `mktemp` + `mv` パターンで中間状態を防止
- **自動updated_at**: `--set` に `updated_at` を含めなければ現在時刻が自動付与される
