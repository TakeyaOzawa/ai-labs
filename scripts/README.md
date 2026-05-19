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

## ディレクトリ構造

```
scripts/
├── pyproject.toml          # プロジェクト設定（pytest, ruff, coverage）
├── Makefile                # テスト・lint実行用
├── conftest.py             # pytest共通fixture（sys.path設定）
├── platform-commands.sh    # シェルユーティリティ
├── _pipeline_common.py     # 後方互換ラッパー（lib/ へのre-export）
│
├── lib/                    # 共通ライブラリ（Pythonパッケージ）
├── pipelines/              # パイプライン実行エントリポイント
├── jobs/                   # ジョブ管理（CRUD + スケジューラ）
├── slack/                  # Slack連携
├── gws/                    # Google Workspace連携
├── data/                   # データ加工・変換
├── rss/                    # RSS/学術フィード
├── ai/                     # AI/エージェント関連
├── setup/                  # セットアップ・検証
├── utils/                  # 汎用ユーティリティ
├── tests/                  # テスト（pytest準拠）
│   ├── unit/               # 単体テスト
│   └── integration/        # 結合テスト
├── git-hooks/              # git hook本体
└── old/                    # 旧スクリプト（参考用）
```

## 主要スクリプト

### pipelines/ — パイプライン実行

| スクリプト | 説明 |
|-----------|------|
| `run-daily-pipeline.py` | デイリーパイプライン実行 |
| `run-weekly-pipeline.py` | ウィークリーパイプライン実行 |
| `run-freshness-pipeline.py` | ディレクトリ鮮度チェックパイプライン |
| `run-poc-planner-pipeline.py` | PoC プランナーパイプライン |
| `run-gws-trend-scout-pipeline.py` | Google Workspace トレンドスカウト |
| `run-academic-trend-scout-pipeline.py` | 学術論文トレンドスカウト |
| `run-github-org-trend-scout-pipeline.py` | GitHub Org トレンドスカウト |
| `run-github-repo-analysis-pipeline.py` | GitHub リポジトリ分析パイプライン |

### slack/ — Slack連携

| スクリプト | 説明 |
|-----------|------|
| `run-slack-dispatch-router.py` | Slack DMポーリング → LLM判定 → エージェント/パイプライン起動 |
| `dispatch-agent-wrapper.py` | エージェント実行ラッパー（完了後にSlack通知） |
| `notify-slack.py` | 汎用Slack通知（Markdown→mrkdwn変換、分割投稿） |
| `fetch-slack-users.py` | Slack APIからユーザー一覧取得 |
| `update-slack-user-directory.py` | Slackユーザーディレクトリ更新 |
| `slack-channel-collector.py` | Slackチャンネル一覧収集 |

### jobs/ — ジョブ管理

| スクリプト | 説明 |
|-----------|------|
| `find-job.py` / `update-job.py` | ジョブ検索・更新 |
| `create-jobs.py` | 汎用ジョブファイル生成 |
| `create-daily-jobs.py` / `create-weekly-jobs.py` | 定期ジョブ生成 |
| `manage-scheduler.py` | launchd スケジューラ管理 |
| `manage-wake-schedule.py` | macOS ウェイクスケジュール管理（pmset） |

### gws/ — Google Workspace連携

| スクリプト | 説明 |
|-----------|------|
| `extract-gws-doc-text.py` | Google Docsテキスト抽出 |
| `extract-gws-sheets-header.py` | Google Sheetsヘッダー抽出 |
| `extract-gws-slides-text.py` | Google Slidesテキスト抽出 |
| `filter-gws-drive-metadata.py` | GWS Driveメタデータフィルタリング |
| `merge-gws-intermediate-files.py` | GWSスカウト中間ファイル統合 |
| `summarize-filtered-metadata.py` | GWS Driveメタデータサマリー生成 |

### rss/ — RSS/学術フィード

| スクリプト | 説明 |
|-----------|------|
| `fetch-rss-feeds.py` | RSSフィード取得（カテゴリ別・日付指定） |
| `rss-source-updater.py` | RSSソース自動発見・更新 |
| `split-academic-feeds.py` | 学術フィードの分野別分割 |
| `merge-academic-intermediate-files.py` | 学術スカウト中間ファイル統合 |

### ai/ — AI/エージェント関連

| スクリプト | 説明 |
|-----------|------|
| `ai-cli-utils.py` | AI CLI ユーティリティ（コマンド構築・エージェント一覧スキャン） |
| `invoke-agent.py` | エージェント手動実行 |
| `resolve-shared-ai-rules.py` | ファイルパスに対応するルール/リファレンスを解決 |
| `sync-claude-agents.py` | .kiro/agents/ → .claude/agents/ の定義同期 |

### setup/ — セットアップ・検証

| スクリプト | 説明 |
|-----------|------|
| `setup-shared-ai.py` | 統合セットアップ（環境変数チェック + symlink構築） |
| `setup-symlinks.py` | AIツール symlink 構築 |
| `verify-shared-ai-structure.py` | .shared-ai 階層構造の整合性検証 |
| `check-env.py` | 環境変数の設定状況チェック |
| `check-directory-freshness.py` | ディレクトリ内ファイルの鮮度チェック |
| `audit-documentation.py` | README/ドキュメントの整合性チェック |

### data/ — データ加工・変換

| スクリプト | 説明 |
|-----------|------|
| `filter-contact-history-csv.py` | 連絡履歴CSVフィルタリング |
| `filter-customer-csv.py` | 顧客CSVフィルタリング |
| `mask-private-csv.py` | CSV内の個人情報マスキング |
| `generate-negotiation-records-sql.py` | 商談レコードSQL生成 |
| `extract-repo-analysis-data.py` | GitHubリポジトリ分析データ抽出 |

### utils/ — 汎用ユーティリティ

| スクリプト | 説明 |
|-----------|------|
| `decode-b64-write.py` | Base64デコード→ファイル書き出し |
| `encode-to-b64.py` | ファイル→Base64エンコード |
| `epoch-to-jst.py` | Unixエポック→JST変換 |
| `get-jst-date.py` | JST日付取得ユーティリティ |
| `free-notion-mcp-port.py` | Notion MCPポート解放 |

### lib/ — 共通ライブラリ

| モジュール | 説明 |
|-----------|------|
| `models.py` | ドメインモデル（Step, Executor, StepParams等） |
| `ports.py` | Protocol定義（SlackNotifier, JobRepository等） |
| `pipeline_engine.py` | パイプライン実行エンジン |
| `slack_client.py` | Slack通知クライアント |
| `job_manager.py` | ジョブファイル管理 |
| `config.py` | 設定・定数の一元管理 |
| `gws_client.py` | GWS API操作共通クラス |
| `logger.py` | 共通ロガー |

## git-hooks/

`scripts/git-hooks/` にはバージョン管理対象の git hook 本体を配置する。
`.git/hooks/` への symlink は `setup-symlinks.py` が管理する。

| フック | 説明 |
|--------|------|
| `pre-commit` | `.shared-ai/` 配下の変更時に構造検証 + `scripts/lib/` 変更時に単体テスト実行 |

## テスト

```bash
# 全テスト実行
make test

# 単体テストのみ
make test-unit

# カバレッジレポート
make coverage

# lint
make lint
```
