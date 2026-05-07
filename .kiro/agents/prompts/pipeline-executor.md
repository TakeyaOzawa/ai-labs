# Pipeline Executor（パイプライン実行手順）

postToolUse(write) hookから呼び出される共通実行手順。
パイプライン種別（daily/weekly）とタスクファイルパスのパターンに基づき、startingタスクを1つ実行する。

## Step 1: startingタスクの検索

```bash
~/scripts/find-task.sh --pipeline {pipeline} --status starting --limit 1
```

`found: false` → 何もせず終了。
`found: true` → `tasks[0]`（対象子タスク）、`parent`（親タスク）、`task_file` を取得。

## Step 2: 依存関係チェック

`depends_on` が null → Step 3へ。

`depends_on` が null でない場合:
```bash
~/scripts/find-task.sh --pipeline {pipeline} --task-name {depends_on} --limit 1
```
- `completed` → Step 3へ
- `pending`/`starting`/`running` → pendingに戻して終了:
  ```bash
  ~/scripts/update-task.sh --task-file {task_file} --task-id {task_id} --set '{"status": "pending", "status_detail": "依存先 {depends_on} の完了待ち"}'
  ```
- `failed` → failedにして終了:
  ```bash
  ~/scripts/update-task.sh --task-file {task_file} --task-id {task_id} --set '{"status": "failed", "error": "依存先 {depends_on} が失敗"}'
  ```

## Step 3: エージェント実行

### 3.1 status を running に更新

現在時刻: `TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00`

```bash
~/scripts/update-task.sh --task-file {task_file} --task-id {task_id} --set '{"status": "running", "started_at": "{現在時刻}"}'
~/scripts/update-task.sh --task-file {task_file} --scope parent --set '{"status_detail": "{task_name} 実行中"}'
```
※ 親タスクの `status` が既に `running` の場合は `status` と `started_at` は省略可。

### 3.2 invokeSubAgent で実行

`task_name` に応じて invokeSubAgent（name: general-task-execution）で委譲。

#### 週次パイプライン（pipeline=weekly）の場合

週次パイプラインモード対象タスク:
- tech-event-scout, lifestyle-event-scout, tech-blog-material-scout, tech-blog-planner

上記タスクの呼び出し:
```
contextFiles: .kiro/agents/prompts/{task_name}.md
プロンプト: {task_name} エージェントとして「週次パイプラインモード」でプロンプトファイルに従い実行してください。基準日は {args.base_date} です。タスクID: {task_id}

【重要: コンテキスト節約ルール】
実行完了時は、以下の簡潔な形式のみで報告すること。レポート全文やファイル内容は返さないこと。

報告フォーマット:
✅ [{task_id}] {task_name} 完了
- 出力ファイル: {パス}
- 件数/概要: {1行サマリー}
- Slack通知: 成功 or 失敗 or なし
- エラー: なし
```

その他のタスク:
```
contextFiles: .kiro/agents/prompts/{task_name}.md
プロンプト: {task_name} エージェントとしてプロンプトファイルに従い実行してください。基準日は {args.base_date} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。タスクID: {task_id}

【重要: コンテキスト節約ルール】（同上）
```

#### 日次パイプライン（pipeline=daily）の場合

全タスク共通:
```
contextFiles: .kiro/agents/prompts/{task_name}.md
プロンプト: {task_name} エージェントとしてプロンプトファイルに従い実行してください。基準日は {args.base_date} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。タスクID: {task_id}

【重要: コンテキスト節約ルール】（同上）
```

### 3.3 完了時の status 更新

正常完了:
```bash
~/scripts/update-task.sh --task-file {task_file} --task-id {task_id} --set '{"status": "completed", "completed_at": "{現在時刻}"}'
```
失敗:
```bash
~/scripts/update-task.sh --task-file {task_file} --task-id {task_id} --set '{"status": "failed", "error": "{エラー内容}"}'
```

### 3.4 後続タスクの起動

```bash
~/scripts/find-task.sh --pipeline {pipeline} --status pending --limit 10
```
`depends_on` が完了したタスクの `task_name` と一致するものがあれば:
```bash
~/scripts/update-task.sh --task-file {task_file} --task-id {該当task_id} --set '{"status": "starting"}'
```

### 3.5 全子タスク完了チェック

```bash
~/scripts/find-task.sh --pipeline {pipeline} --status starting --limit 1
~/scripts/find-task.sh --pipeline {pipeline} --status running --limit 1
~/scripts/find-task.sh --pipeline {pipeline} --status pending --limit 1
```

全て `found: false` の場合:
```bash
~/scripts/find-task.sh --pipeline {pipeline} --status failed --limit 10
```
- 全completed → 親タスクを completed に
- 1つでもfailed → 親タスクを failed に

親タスクを completed/failed にした場合 → Step 5へ。

## Step 4: 再発火トリガー

全子タスク完了に至らなかった場合、タスクファイルの親タスク `updated_at` を strReplace で現在時刻に更新する。

1. `TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00` で現在時刻取得
2. タスクファイルをreadFileで読み、親タスクの `updated_at` を確認
3. strReplace で更新

※ 1回のhook発火で処理するタスクは常に1つだけ。
※ 全子タスク完了時は strReplace を行わない。

## Step 5: 完了報告

「✅ [{task_id}] {task_name}（基準日: {args.base_date}）の実行が完了しました。」と報告。
全子タスク完了時は親タスクの最終ステータスも報告。

### 完了マーカー（postToolUse発火用）

親タスクを completed/failed にした場合、タスクファイルの親タスク `status_detail` を strReplace で最終値に更新する。
この strReplace が postToolUse(write) を発火させ、後続hook（reference-data-refresh等）のトリガーとなる。

手順:
1. タスクファイルをreadFileで読み、親タスクの現在の `status_detail` を確認
2. strReplace で `"status_detail": "{現在値}"` → `"status_detail": "全子タスク完了"` または `"status_detail": "{N}件失敗"` に更新

※ Step 3.5 で update-task.sh により既に更新済みの値と同一になるが、strReplace による write 発火が目的。
