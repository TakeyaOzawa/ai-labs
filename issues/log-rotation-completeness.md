# ログローテーション完全適用

## 変更種別

fix

## 概要

- `scout-daily-slack-notify.log` / `scout-weekly-slack-notify.log` にローテーション追加
- `scout-daily-pipeline-error.log` / `scout-weekly-pipeline-error.log` にローテーション追加
- error.logに「親タスク > 子タスク」の2階層ヘッダーを付与して構造化

## 問題・背景

- Python版パイプラインスクリプトで通知ログとerror.logにローテーションが未適用
- error.logはlaunchdのStandardErrorPathで出力されるが、Python未捕捉例外時にどのタスクで発生したか不明

## 修正対象

- `~/scripts/run-daily-pipeline.py`
- `~/scripts/run-weekly-pipeline.py`

## タスク分解

### Task 1: slack-notify.log ローテーション追加

- **対象ファイル:** run-daily-pipeline.py, run-weekly-pipeline.py
- **変更内容:** Slack通知ステップ開始前に `rotate_log(notify_log, MAX_AGENT_LOG_LINES, keep_lines=100)` を追加

### Task 2: error.log ローテーション追加

- **対象ファイル:** run-daily-pipeline.py, run-weekly-pipeline.py
- **変更内容:** main()冒頭で `rotate_log(error_log, MAX_LOG_LINES)` を追加

### Task 3: error.log 構造化出力

- **対象ファイル:** run-daily-pipeline.py, run-weekly-pipeline.py
- **変更内容:** stderrに「[pipeline] > [agent]」形式のヘッダーを出力するエラーハンドリング追加

## 影響範囲

- パイプライン実行時のログ出力のみ。機能的な変更なし

## テスト計画

- [ ] 各ログファイルに対して rotate_log が呼ばれることをコードで確認
- [ ] error.log出力時に親タスク・子タスクの階層が表示されることを確認
