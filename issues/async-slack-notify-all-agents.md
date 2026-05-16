# async-slack-notify-all-agents: 全エージェントの非同期Slack通知対応

## 変更種別

feat

## 概要

- 全エージェントで処理完了時にSlack通知を実行する仕組みに変更
- 通知は新規プロセスで非同期に実行（fire-and-forget）
- 現在通知していないエージェントは初期状態で `enabled=False`

## 問題・背景

- 現在は `NOTIFY_FILE_MAP` に登録されたエージェントのみ同期的に通知
- 通知処理がパイプライン全体の実行時間を延長している
- 新規エージェント追加時に通知設定の明示性が低い

## 修正対象

- `scripts/_pipeline_common.py` — 通知ロジックの非同期化
- `scripts/run-daily-pipeline.py` — `NOTIFY_FILE_MAP` → `NOTIFY_CONFIG` 拡張
- `scripts/run-weekly-pipeline.py` — 同上
- `scripts/notify-slack.py` — 変更なし（呼び出し側のみ変更）

## タスク分解

### Task 1: `_pipeline_common.py` の通知ロジック非同期化

- **対象ファイル:** `scripts/_pipeline_common.py`
- **変更内容:**
  - `run_slack_notify()` に加え、`run_slack_notify_async()` を追加（`subprocess.Popen` でfire-and-forget）
  - Step 4 の通知ループで `run_slack_notify_async()` を使用
  - `NOTIFY_FILE_MAP` の型を `dict[str, str]` から `dict[str, NotifyEntry]` に変更対応
  - `NotifyEntry` dataclass: `template: str`, `enabled: bool = True`
  - 非同期プロセスのPIDをログに記録

### Task 2: `run-daily-pipeline.py` の通知設定拡張

- **対象ファイル:** `scripts/run-daily-pipeline.py`
- **変更内容:**
  - `NOTIFY_FILE_MAP` を `NOTIFY_CONFIG` に変更
  - 全エージェントのエントリを追加（現在通知なしのものは `enabled=False`）
  - `lifestyle-event-scout` の動的解決は維持

### Task 3: `run-weekly-pipeline.py` の通知設定拡張

- **対象ファイル:** `scripts/run-weekly-pipeline.py`
- **変更内容:**
  - `NOTIFY_FILE_MAP` を `NOTIFY_CONFIG` に変更
  - 全エージェントのエントリを追加（現在通知なしのものは `enabled=False`）

## 影響範囲

- 日次・週次パイプラインの通知動作
- `agent-pipeline-guide.md` のドキュメント（NOTIFY_FILE_MAP → NOTIFY_CONFIG の記載更新）
- `agent-creator.md` のSlack通知に関する記載

## テスト計画

- [ ] dailyパイプラインで通知対象エージェントが非同期で通知されること
- [ ] `enabled=False` のエージェントが通知されないこと
- [ ] 通知プロセスの失敗がパイプライン本体に影響しないこと
