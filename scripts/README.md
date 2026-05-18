# scripts/

個人用自動化スクリプト群。パイプライン実行、Slack連携、ジョブ管理などを担う。

## 環境変数

### セットアップ手順

1. `~/.zshrc` に以下の `export` 行を追加する
2. `scripts/platform-commands.sh` の `source-env` セクション内の grep パターンに変数名を追加する（launchd 経由の定期実行で読み込まれるようにするため）

### 必須環境変数

| 変数名 | 用途 | 使用スクリプト |
|--------|------|----------------|
| `MY_SLACK_OAUTH_TOKEN` | Slack Bot Token（xoxb-...） | `run-slack-dispatch-router.py`, `notify-slack.py` |
| `SLACK_DISPATCH_DM_CHANNEL` | ディスパッチ対象のSlack DMチャンネルID | `run-slack-dispatch-router.py`, `notify-slack.py` |
| `SLACK_DISPATCH_TARGET_USER` | ディスパッチ対象のSlackユーザーID | `run-slack-dispatch-router.py` |

### オプション環境変数

| 変数名 | 用途 | デフォルト |
|--------|------|------------|
| `SLACK_REFERENCE_BOT_TOKEN` | Slack参照用Bot Token | — |
| `SLACK_REFERENCE_TEAM_ID` | Slack参照用チームID | — |
| `AI_COMMAND_TYPE` | AI CLIの種類（`claude` or `kiro-cli`） | `claude` |
| `GH_REFERENCE_TOKEN` | GitHub Personal Access Token | — |
| `DEVELOPER_AI_NOTION_TOKEN` | Notion API トークン | — |
| `GITHUB_ORG_NAME` | GitHub Organization名 | — |

### `platform-commands.sh source-env` で管理される変数

launchd 等の非インタラクティブ環境から実行される場合、`load_env()` が `platform-commands.sh source-env` を呼び出して `.zshrc` から以下の変数を読み込む:

```
MY_SLACK_OAUTH_TOKEN
SLACK_REFERENCE_BOT_TOKEN
SLACK_REFERENCE_TEAM_ID
SLACK_DISPATCH_DM_CHANNEL
SLACK_DISPATCH_TARGET_USER
GH_REFERENCE_TOKEN
DEVELOPER_AI_NOTION_TOKEN
GITHUB_ORG_NAME
AI_COMMAND_TYPE
```

新しい環境変数を追加する場合は、`.zshrc` への export 追加に加えて、`platform-commands.sh` 内の grep パターン（2箇所: eval行とenv行）にも追加すること。

## 主要スクリプト

| スクリプト | 説明 |
|-----------|------|
| `run-slack-dispatch-router.py` | Slack DMポーリング → LLM判定 → エージェント/パイプライン起動 |
| `dispatch-agent-wrapper.py` | エージェント実行ラッパー（完了後にSlack通知） |
| `invoke-agent.py` | エージェント手動実行（agent_params YAML生成 + AI CLI呼び出し） |
| `notify-slack.py` | 汎用Slack通知（Markdown→mrkdwn変換、分割投稿） |
| `setup-shared-ai.py` | 統合セットアップ（環境変数チェック + symlink構築） |
| `check-env.py` | 環境変数の設定状況チェック |
| `setup-symlinks.py` | AIツール symlink 構築（.shared-ai → 各ツール設定ディレクトリ） |
| `verify-shared-ai-structure.py` | .shared-ai 階層構造の整合性検証（構造・steering・symlink・旧パス等） |
| `audit-documentation.py` | README/ドキュメントの整合性チェック（リンク・対応表・命名規則等） |
| `ai-cli-utils.py` | AI CLI ユーティリティ（コマンド構築・エージェント一覧スキャン） |
| `sync-claude-agents.py` | .kiro/agents/ → .claude/agents/ の定義同期 |
| `resolve-shared-ai-rules.py` | ファイルパスに対応するルール/リファレンスを解決 |
| `run-daily-pipeline.py` | デイリーパイプライン実行 |
| `run-weekly-pipeline.py` | ウィークリーパイプライン実行 |
| `run-gws-trend-scout-pipeline.py` | Google Workspace トレンドスカウト |
| `run-academic-trend-scout-pipeline.py` | 学術論文トレンドスカウト |
| `run-github-org-trend-scout-pipeline.py` | GitHub Org トレンドスカウト |
| `run-github-repo-analysis-pipeline.py` | GitHub リポジトリ分析パイプライン |
| `run-poc-planner-pipeline.py` | PoC プランナーパイプライン |
| `run-freshness-pipeline.py` | ディレクトリ鮮度チェックパイプライン |
| `platform-commands.sh` | OS操作ユーティリティ（caffeinate, launchctl, source-env等） |
| `find-job.py` / `update-job.py` | ジョブ検索・更新 |
| `create-jobs.py` | 汎用ジョブファイル生成 |
| `create-daily-jobs.py` / `create-weekly-jobs.py` | 定期ジョブ生成 |
| `manage-scheduler.py` | launchd スケジューラ管理 |
| `manage-wake-schedule.py` | macOS ウェイクスケジュール管理（pmset） |
| `fetch-rss-feeds.py` | RSSフィード取得（カテゴリ別・日付指定） |
| `split-academic-feeds.py` | 学術フィードの分野別分割 |
| `merge-academic-intermediate-files.py` | 学術スカウト中間ファイル統合 |
| `merge-gws-intermediate-files.py` | GWSスカウト中間ファイル統合 |
| `rss-source-updater.py` | RSSソース自動発見・更新（レポートから未登録サイト検出） |
| `fetch-slack-users.py` | Slack APIからユーザー一覧取得 |
| `update-slack-user-directory.py` | Slackユーザーディレクトリ更新 |
| `slack-channel-collector.py` | Slackチャンネル一覧収集 |
| `extract-gws-doc-text.py` | Google Docsテキスト抽出 |
| `extract-gws-sheets-header.py` | Google Sheetsヘッダー抽出 |
| `extract-gws-slides-text.py` | Google Slidesテキスト抽出 |
| `extract-repo-analysis-data.py` | GitHubリポジトリ分析データ抽出 |
| `summarize-filtered-metadata.py` | GWS Driveメタデータサマリー生成 |
| `filter-gws-drive-metadata.py` | GWS Driveメタデータフィルタリング |
| `filter-contact-history-csv.py` | 連絡履歴CSVフィルタリング |
| `filter-customer-csv.py` | 顧客CSVフィルタリング |
| `check-directory-freshness.py` | ディレクトリ内ファイルの鮮度チェック |
| `free-notion-mcp-port.py` | Notion MCPポート解放 |
| `get-jst-date.py` | JST日付取得ユーティリティ |
| `epoch-to-jst.py` | Unixエポック→JST変換 |
| `decode-b64-write.py` | Base64デコード→ファイル書き出し |
| `encode-to-b64.py` | ファイル→Base64エンコード |
| `mask-private-csv.py` | CSV内の個人情報マスキング |
| `generate-negotiation-records-sql.py` | 商談レコードSQL生成 |

### 内部モジュール

| モジュール | 説明 |
|-----------|------|
| `_pipeline_common.py` | パイプライン共通基盤（Step, Executor, PipelineConfig等） |
| `_version_check.py` | Python 3.12バージョンチェック |
| `logger.py` | 共通ロガー（get_logger, log_error, rotate_log） |

## git-hooks/

`scripts/git-hooks/` にはバージョン管理対象の git hook 本体を配置する。
`.git/hooks/` への symlink は `setup-symlinks.py` が管理する。

| フック | 説明 |
|--------|------|
| `pre-commit` | `.shared-ai/` 配下の変更時に `verify-shared-ai-structure.py` を自動実行 |
