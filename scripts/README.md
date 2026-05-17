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
| `notify-slack.py` | 汎用Slack通知（Markdown→mrkdwn変換、分割投稿） |
| `setup-shared-ai.py` | 統合セットアップ（環境変数チェック + symlink構築） |
| `check-env.py` | 環境変数の設定状況チェック |
| `setup-symlinks.py` | AIツール symlink 構築（.shared-ai → 各ツール設定ディレクトリ） |
| `verify-shared-ai-structure.py` | .shared-ai 階層構造の整合性検証（構造・steering・symlink・旧パス等） |
| `ai-command-builder.py` | AIコマンド構築ユーティリティ（claude / kiro-cli 対応） |
| `resolve-shared-ai-rules.py` | ファイルパスに対応するルール/リファレンスを解決 |
| `run-daily-pipeline.py` | デイリーパイプライン実行 |
| `run-weekly-pipeline.py` | ウィークリーパイプライン実行 |
| `run-gws-trend-scout-pipeline.py` | Google Workspace トレンドスカウト |
| `run-academic-trend-scout-pipeline.py` | 学術論文トレンドスカウト |
| `run-github-org-trend-scout-pipeline.py` | GitHub Org トレンドスカウト |
| `platform-commands.sh` | OS操作ユーティリティ（caffeinate, launchctl, source-env等） |
| `find-job.py` / `update-job.py` | ジョブ検索・更新 |
| `create-daily-jobs.py` / `create-weekly-jobs.py` | 定期ジョブ生成 |
| `manage-scheduler.py` | launchd スケジューラ管理 |
