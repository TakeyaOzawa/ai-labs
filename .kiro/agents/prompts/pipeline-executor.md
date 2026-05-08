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
- tech-event-scout, lifestyle-event-scout, tech-blog-material-scout, tech-poc-planner, github-verification-candidate-scout

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

## Step 5: Slack通知（全子タスク完了時のみ）

親タスクを completed/failed にした場合（= 全子タスク完了時）、完了した各scoutの出力ファイルをSlack通知する。

### 5.1 通知対象ファイルの特定

以下のマッピングに基づき、completedステータスの子タスクの出力ファイルパスを特定する:

| task_name | 出力ファイルパス |
|---|---|
| tech-trend-scout | `~/Documents/works/scout_histories/tech_trends/daily/{base_date}_tech_trends.md` |
| biz-car-trend-scout | `~/Documents/works/scout_histories/biz_car_trends/daily/{base_date}_biz_car_trends.md` |
| academic-trend-scout | `~/Documents/works/scout_histories/academic_trends/daily/{base_date}_academic_trends.md` |
| gws-trend-scout | `~/Documents/works/scout_histories/gws_trends/daily/{base_date}_gws_daily.md` |
| slack-trend-scout | `~/Documents/works/scout_histories/slack_trends/daily/{base_date}_slack_daily.md` |
| github-org-trend-scout | `~/Documents/works/scout_histories/github_org_trends/daily/{base_date}_github-org_daily.md` |
| github-public-trend-scout | `~/Documents/works/scout_histories/github_public_trends/daily/{base_date}_github-public_daily.md` |
| notion-trend-scout | `~/Documents/works/scout_histories/notion_trends/daily/{base_date}_notion_daily.md` |
| slack-digest-scout | `~/Documents/works/scout_histories/slack_trends/weekly/{base_date}_slack_weekly_digest.md` |
| gws-digest-scout | `~/Documents/works/scout_histories/gws_trends/weekly/{base_date}_gws_weekly_digest.md` |
| notion-digest-scout | `~/Documents/works/scout_histories/notion_trends/weekly/{base_date}_notion_weekly_digest.md` |
| github-org-digest-scout | `~/Documents/works/scout_histories/github_org_trends/weekly/{base_date}_github-org_weekly_digest.md` |
| github-public-digest-scout | `~/Documents/works/scout_histories/github_public_trends/weekly/{base_date}_github-public_weekly_digest.md` |
| tech-event-scout | `~/Documents/works/scout_histories/tech_events/weekly/{base_date}_tech_events.md` |
| lifestyle-event-scout | `~/Documents/works/scout_histories/lifestyle_events/weekly/{base_date}_lifestyle_events.md` |

※ 上記マッピングに無い task_name（tech-blog-material-scout, tech-poc-planner, github-verification-candidate-scout 等）は通知スキップ。

### 5.2 通知実行

completedの子タスクについて、出力ファイルが存在するもののパスを収集し、invokeSubAgent で一括通知を委譲する:

```
name: general-task-execution
contextFiles: .kiro/agents/prompts/slack-notifier.md
プロンプト:
  slack-notifier エージェントとして動作してください。
  以下のファイルを順番にSlack通知してください。
  各ファイルについて、readFile→Markdown変換→投稿を行ってください。
  channel_id: U076LRL1B35

  通知対象ファイル:
  1. {file_path_1}
  2. {file_path_2}
  ...

  【重要: コンテキスト節約ルール】
  - 各ファイルは読み込み→変換→投稿→次のファイルへ進む。変換前の原文は保持不要。
  - 完了報告は以下の簡潔な形式のみ:
    ✅ Slack通知完了: {N}件投稿 / {M}件スキップ
```

※ failedの子タスクは通知スキップ（出力ファイルが存在しない想定）。
※ 出力ファイルが存在しない場合もスキップ。

### 5.3 コンテキスト節約の設計意図

1エージェントで全ファイルを処理する方式を採用。理由:
- 各ファイルの処理は独立（read→convert→post）で、前のファイル内容を保持する必要がない
- Slack投稿APIの呼び出し自体は軽量（レスポンスが小さい）
- 8ファイル × 平均15KB = 120KB程度のコンテキスト消費は許容範囲内
- invokeSubAgentを8回呼ぶよりも、1回で済ませる方がpipeline-executor側のコンテキストを節約できる

万が一コンテキスト超過で途中失敗した場合でも、既に投稿済みのメッセージは残るため、部分的成功として許容する。

## Step 6: 完了報告

「✅ [{task_id}] {task_name}（基準日: {args.base_date}）の実行が完了しました。」と報告。
全子タスク完了時は親タスクの最終ステータスとSlack通知結果も報告。

### 完了マーカー（postToolUse発火用）

親タスクを completed/failed にした場合、タスクファイルの親タスク `status_detail` を strReplace で最終値に更新する。
この strReplace が postToolUse(write) を発火させ、後続hook（reference-data-refresh等）のトリガーとなる。

手順:
1. タスクファイルをreadFileで読み、親タスクの現在の `status_detail` を確認
2. strReplace で `"status_detail": "{現在値}"` → `"status_detail": "全子タスク完了"` または `"status_detail": "{N}件失敗"` に更新

※ Step 3.5 で update-task.sh により既に更新済みの値と同一になるが、strReplace による write 発火が目的。
※ Slack通知（Step 5）は完了マーカーの前に実行する。通知失敗はパイプライン全体の成否に影響しない。
