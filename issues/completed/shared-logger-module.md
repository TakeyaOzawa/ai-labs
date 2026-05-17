# shared-logger-module: 共通ロガーモジュール新設

## 変更種別

refactor

## 概要

- パイプラインおよび各種ユーティリティスクリプトのログ出力処理を `scripts/logger.py` に集約する
- `PipelineLogger` クラスで自プロセスのログ出力と子プロセスのログファイルローテーションを一元管理する
- コンテキスト圧縮、フォーマット共通化、ログローテーション品質の均一化を実現する
- マルチプラットフォーム動作を前提とし、将来的なCloudWatch等クラウドサービスへの移行パスも確保する

## 完了済みタスク

### Task 1: logger.py 基本実装 ✅

- `PipelineLogger` クラス（自プロセスログ + 子プロセスログファイル管理の統合）
- `PipelineFormatter`（既存の `[timestamp] emoji message` 形式を再現）
- `JsonFormatter`（CloudWatch等向けJSON出力、`LOG_FORMAT=json` で切替）
- `RotatingLineHandler`（行数ベースローテーション）
- 後方互換: `get_logger()`, `rotate_log()`, `log_error()`
- 環境変数制御: `LOG_LEVEL`, `LOG_FORMAT`

### Task 2: _pipeline_common.py 統合 ✅

- `run_pipeline()` を `PipelineLogger` ベースに全面書き換え
- 全 `print(f"[{now_jst()}] ...")` → `plogger.info/warning/error()` に置換
- 全 `rotate_log(agent_log, ...)` → `plogger.get_agent_log(entry_name)` に置換
- `log_error(...)` → `plogger.log_error(...)` に置換
- `rotate_log()`, `log_error()` は後方互換として re-export 維持

### ドキュメント更新 ✅

- `~/.shared-ai/rules/python-coding-standards.md` — Section 8 に logger.py 使用ルール追加
- `~/.shared-ai/references/agent-pipeline-run-script-guide.md` — PipelineLogger API文書、実行フロー、テンプレート更新
- `~/.shared-ai/prompts/agent-pipeline-creator.md` — ログ管理の記述を PipelineLogger に更新
- `~/issues/shared-logger-module.md` — 本ファイル

## 残課題

### Task 3: メインパイプラインのコールバック移行（P1）

**対象ファイル・print()残存数:**

| ファイル | print()数 | 内容 |
|----------|-----------|------|
| `run-daily-pipeline.py` | 6 | `_sync_claude_agents`, `_rss_fetch_hook` コールバック内 |
| `run-weekly-pipeline.py` | 19 | `run_poc_planner`, `run_freshness_check` コールバック内 |
| `_pipeline_common.py` | 2 | `_print_retry_hint` 関数（モジュールレベル関数のため `plogger` アクセス不可） |

**移行方針:**
- コールバック関数内: `from logger import get_logger` で個別ロガーを取得して使用
- `_print_retry_hint`: `plogger` を引数で受け取るか、`get_logger(config.name)` で取得（既にハンドラ設定済みのロガーが返る）
- `run-weekly-pipeline.py` の `rotate_log()` / `log_error()` 直接呼び出し（3+3=6箇所）: 後方互換関数で動作するため急ぎではないが、将来的に `PipelineLogger` インスタンスをコールバックに渡す設計に統一すべき

### Task 4: サブパイプライン移行（P2）

**対象ファイル・print()残存数:**

| ファイル | print()数 | 備考 |
|----------|-----------|------|
| `run-academic-trend-scout-pipeline.py` | 29 | 独自実行ロジックあり |
| `run-gws-trend-scout-pipeline.py` | 29 | 独自実行ロジックあり |
| `run-github-repo-analysis-pipeline.py` | 43 | 独自実行ロジックあり |
| `run-github-org-trend-scout-pipeline.py` | 0 | ✅ 移行不要（`run_pipeline()` に委譲済み） |
| `run-slack-dispatch-router.py` | 5 | ルーティングスクリプト |

**移行方針:**
- `run_pipeline()` を使用しているスクリプト（github-org）は移行不要
- 独自実行ロジックを持つスクリプト（academic, gws, github-repo）は `PipelineLogger` または `get_logger()` に段階的に移行
- `run-slack-dispatch-router.py` は軽量なので `get_logger()` で対応

### Task 5: ユーティリティスクリプト移行（P3）

**対象: 35本**（logger.py, _pipeline_common.py, _version_check.py, パイプラインスクリプトを除く）

**分類:**

| カテゴリ | スクリプト数 | 移行方針 |
|----------|-------------|----------|
| JSON出力のみ（`print(json.dumps(...))`） | ~10本 | 移行不要（最終出力はlogger対象外） |
| stderr進捗 + JSON出力 | ~10本 | stderr部分のみ `get_logger()` に移行 |
| 進捗表示のみ | ~15本 | `get_logger()` に移行 |

**代表的なスクリプトと対応:**

| スクリプト | print()数 | 用途 | 移行優先度 |
|------------|-----------|------|-----------|
| `notify-slack.py` | 11 | Slack通知 | 低（独立動作、頻繁に変更しない） |
| `fetch-rss-feeds.py` | 8 | RSS取得 | 低 |
| `fetch-slack-users.py` | 多 | Slackユーザー取得 | 低 |
| `create-daily-jobs.py` | 2 | ジョブ生成 | 低（JSON出力のみ） |
| `find-job.py` | 4 | ジョブ検索 | 低（JSON出力のみ） |
| `update-job.py` | 4 | ジョブ更新 | 低（JSON出力のみ） |
| `check-directory-freshness.py` | 3 | 鮮度チェック | 低（JSON出力のみ） |

### Task 6: JsonFormatter拡張（Phase 2準備）

- `JsonFormatter` は基本実装済み（`LOG_FORMAT=json` で切替可能）
- 追加フィールド: `pipeline`, `agent`, `duration`, `success_rate` 等のメトリクス埋め込み
- CloudWatch Logs Handler の設計（boto3遅延import、バッチ送信）

## 今後の対応方針

### 優先度と実施タイミング

| 優先度 | タスク | タイミング | 理由 |
|--------|--------|-----------|------|
| 中 | Task 3 | 次回パイプライン改修時 | コールバック内のprint()は動作に影響なし。改修のついでに対応 |
| 低 | Task 4 | サブパイプライン改修時 | 独自ロジックの書き換えは影響範囲が大きい |
| 最低 | Task 5 | 各スクリプト改修時 | JSON出力スクリプトは移行不要。その他も急ぎではない |
| 将来 | Task 6 | クラウド移行検討時 | 現時点では不要 |

### PipelineLogger をコールバックに渡す設計（Task 3 実施時の検討事項）

`run-weekly-pipeline.py` の `run_poc_planner()` / `run_freshness_check()` は `post_agents_hook` / `post_notify_hook` コールバックとして呼ばれる。現在のシグネチャは `(base_date: str) -> None` で `PipelineLogger` を受け取れない。

**選択肢:**
1. `PipelineConfig` に `plogger` フィールドを追加（侵襲的）
2. コールバックシグネチャを `(base_date: str, plogger: PipelineLogger) -> None` に変更（破壊的）
3. コールバック内で `get_logger(config.name)` を呼ぶ（既にハンドラ設定済みのロガーが返る。非侵襲的）
4. グローバル変数で `plogger` を共有（非推奨）

**推奨: 選択肢3**（`get_logger()` は既存ハンドラを再利用するため、`PipelineLogger` と同一のロガーインスタンスが返る）

## テスト計画

- [x] PipelineLogger: info/warning/error がコンソール + ファイルに出力される
- [x] PipelineLogger: get_agent_log() がパスを返し、事前ローテーションが動作する
- [x] PipelineLogger: rotate_all() が pipeline-error.log をローテーションする
- [x] PipelineLogger: log_error() が stderr に出力される
- [x] 後方互換: `get_logger()`, `rotate_log()`, `log_error()` の既存呼び出しが動作する
- [x] パイプライン実行: run_pipeline() が正常に動作する（end-to-end テスト済み）
- [x] LOG_LEVEL / LOG_FORMAT 環境変数による制御が動作する
- [ ] Task 3 実施後: コールバック内のログ出力が pipeline.log に記録される
- [ ] Task 4 実施後: サブパイプラインのログ出力が統一フォーマットになる
