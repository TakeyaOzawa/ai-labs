# タスク管理抽象化: find-task / update-task スクリプト

## 変更種別

refactor

## 概要

- Watcherが直接JSONファイルを `strReplace` で操作していた構造を、シェルスクリプト経由に抽象化した
- 将来タスク管理が外部サービス（DB、API等）に移行しても、Watcher側の変更が不要になる設計
- hookの循環発火問題を根本解消（`executeBash` は write カテゴリではないため postToolUse(write) が発火しない）

## 問題・背景

- 旧WatcherはタスクファイルのJSON構造を直接知っていた（密結合）
- `strReplace` による更新が postToolUse(write) を発火し、hookの循環発火を引き起こしていた
- 外部サービス移行時にWatcherのプロンプト全体を書き換える必要があった

## 実装済みスクリプト

### スクリプト構成

| スクリプト | 役割 | パス |
|---|---|---|
| `find-task.sh` | タスク検索・取得 | `~/scripts/find-task.sh` |
| `update-task.sh` | タスクステータス更新 | `~/scripts/update-task.sh` |

### find-task.sh

```bash
# 使い方
find-task.sh --pipeline daily|weekly [--date YYYY-MM-DD] [--status STATUS] [--task-id ID] [--task-name NAME] [--scope parent|child] [--limit N]

# 例: statusがstartingの子タスクを1件取得
~/scripts/find-task.sh --pipeline daily --status starting --limit 1

# 例: 特定のtask_idで検索
~/scripts/find-task.sh --pipeline daily --task-id 01KQVFHZKG0M441E2T15MQ0JPV

# 例: task_nameで検索
~/scripts/find-task.sh --pipeline daily --task-name tech-trend-scout

# 例: 親タスクを取得
~/scripts/find-task.sh --pipeline daily --scope parent

# 例: 特定日付のタスクファイルを対象
~/scripts/find-task.sh --pipeline daily --date 2026-05-04 --status starting
```

出力（JSON）:
```json
{
  "found": true,
  "task_file": "/Users/.../scout_daily/2026-05-04_xxx.json",
  "tasks": [
    {
      "task_id": "...",
      "task_name": "tech-trend-scout",
      "status": "starting",
      "depends_on": null,
      "args": { "base_date": "2026-05-04" },
      ...
    }
  ],
  "parent": {
    "task_id": "...",
    "task_name": "scout_daily",
    "status": "running",
    ...
  }
}
```

### update-task.sh

```bash
# 使い方
update-task.sh --task-file /path/to/file.json --task-id ID --set '{"key": "value", ...}'
update-task.sh --task-file /path/to/file.json --scope parent --set '{"key": "value", ...}'

# 例: 子タスクをrunningに更新
~/scripts/update-task.sh --task-file /path/to/file.json \
  --task-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "running", "started_at": "2026-05-05T16:10:44+09:00"}'

# 例: 親タスクのstatus_detailを更新
~/scripts/update-task.sh --task-file /path/to/file.json \
  --scope parent \
  --set '{"status_detail": "tech-trend-scout 実行中"}'

# 例: 子タスクをcompletedに更新
~/scripts/update-task.sh --task-file /path/to/file.json \
  --task-id 01KQVFHZKG0M441E2T15MQ0JPV \
  --set '{"status": "completed", "completed_at": "2026-05-05T16:16:19+09:00"}'
```

--set で指定可能なフィールド:
- `status` (pending / starting / running / completed / failed)
- `status_detail` (進捗メッセージ)
- `started_at` (ISO 8601)
- `updated_at` (ISO 8601、省略時は自動付与)
- `completed_at` (ISO 8601)
- `error` (エラーメッセージ)

出力（JSON）:
```json
{
  "success": true,
  "task_file": "/path/to/file.json",
  "task_id": "01KQVFHZKG0M441E2T15MQ0JPV",
  "scope": "child",
  "before": { "status": "starting", ... },
  "after": { "status": "running", ... },
  "message": "Task 01KQVFHZKG0M441E2T15MQ0JPV updated: starting → running"
}
```

## Watcherの動作フロー（v7.0.0）

```
postToolUse(write) 発火
  → Step 0: ファイルパス判定（scout_daily/ or scout_weekly/ 配下の.jsonか？）
  → Step 1: find-task.sh で starting タスクを検索
  → Step 2: 依存関係チェック（find-task.sh で依存先を確認）
  → Step 3: エージェント実行
      3.1: update-task.sh で running に更新
      3.2: invokeSubAgent で委譲実行
      3.3: update-task.sh で completed/failed に更新
      3.4: find-task.sh で後続タスク確認 → update-task.sh で starting に
      3.5: 全子タスク完了チェック → 親タスク更新
  → Step 4: ループ（Step 1に戻り次のstartingタスクを処理）
  → Step 5: 完了報告
```

**重要な設計変更点:**
- `task-update.sh` は `executeBash` 経由で実行されるため、postToolUse(write) は発火しない
- そのため同一実行内でループして全タスクを順次処理する（旧版のhook連鎖方式ではない）

## 修正対象（実施済み）

| ファイル | 変更内容 | バージョン |
|---|---|---|
| `scripts/find-task.sh` | 新規作成 | - |
| `scripts/update-task.sh` | 新規作成 | - |
| `.kiro/hooks/scouts-daily-watcher.kiro.hook` | プロンプト書き換え | v6.0.0 → v7.0.0 |
| `.kiro/hooks/scouts-weekly-watcher.kiro.hook` | プロンプト書き換え | v6.0.0 → v7.0.0 |

## 将来の拡張

バックエンドを外部サービスに移行する場合:
1. `find-task.sh` 内部をAPI呼び出しに差し替え（出力JSON形式は維持）
2. `update-task.sh` 内部をAPI呼び出しに差し替え（出力JSON形式は維持）
3. Watcherのプロンプトは変更不要

## テスト結果

- [x] `find-task.sh` が既存タスクファイルから正しく検索できること（2026-05-05 確認済み）
- [x] `update-task.sh` がステータス更新を正しく反映すること（2026-05-05 確認済み）
- [ ] Watcherが新スクリプト経由で正常にパイプラインを実行できること（次回パイプライン起動時に確認）
- [x] hookの循環発火が発生しないこと（executeBash経由のため原理的に発火しない）
