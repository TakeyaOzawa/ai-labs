# エージェント作成ガイド

scoutパイプライン等のエージェントを新規作成・改修する際の設計基準。
既存の `*-trend-scout` / `*-event-scout` / `*-digest-scout` の実装パターンに基づく。

詳細な実装パターンは以下の参照ファイルを参照:
- `agent-prompt-patterns.md` — コンテキスト節約、2段階実行、テーマ分割、コマンド抽象化
- `scout-pipeline-integration.md` — hook連携、パイプライン組み込み、低頻度更新データ設計

## 命名規則

### 区切り文字

| 対象 | 規則 | 区切り | 例 |
|------|------|--------|-----|
| エージェント名 | ケバブケース | `-` | `tech-trend-scout` |
| プロンプトファイル名 | ケバブケース | `-` | `tech-trend-scout.md` |
| hookファイル名 | ケバブケース | `-` | `scouts-weekly-watcher.kiro.hook` |
| スクリプトファイル名 | ケバブケース | `-` | `find-task.sh` |
| referencesファイル名 | ケバブケース | `-` | `tech-trend-sources.md` |
| steeringファイル名 | ケバブケース | `-` | `agent-creation-guide.md` |
| 出力ディレクトリ名 | スネークケース | `_` | `tech_trends`, `slack_trends` |
| 出力ファイル名 | `{日付}_{テーマkebab}_{種別}.md` | `_`=構造区切り、`-`=単語区切り | `2026-05-05_aws-bedrock_material.md` |

**理由**:
- 設定・定義ファイル（人が管理）: `-` で統一。Kiroの慣習・URL慣習に準拠
- 出力ディレクトリ（プログラムが参照）: `_` で統一。シェル変数代入・split処理が容易
- 出力ファイル名: `_` で split すれば `[日付, テーマ, 種別]` に構造的にパース可能

### ファイル名の語形規則

| 対象 | 語形 | パターン | 良い例 | 悪い例 |
|------|------|----------|--------|--------|
| エージェント名 | **名詞（役割）** | `{領域}-{機能}-{役割}` | `tech-trend-scout` | `scout-tech-trends` |
| hookファイル名 | **名詞（イベント/動作名）** | `{対象}-{動作名}` | `reference-data-refresh` | `refresh-reference-data` |
| steeringファイル名 | **名詞（文書種別）** | `{トピック}-{文書種別}` | `agent-creation-guide` | `guide-for-creating-agents` |
| スクリプトファイル名 | **動詞始まり（コマンド）** | `{動詞}-{対象}` | `find-task.sh`, `create-weekly-tasks.sh` | `task-finder.sh` |
| referencesファイル名 | **名詞（データ種別）** | `{エージェント名}-sources` | `tech-trend-sources.md` | `sources-for-tech-trend.md` |

### 詳細ルール

#### エージェント名: `{領域}-{機能}-{役割}`

役割を表す名詞で終わる。「何者か」が一目で分かる命名。

| 役割語 | 意味 | 例 |
|--------|------|-----|
| `scout` | 情報収集・偵察 | `tech-trend-scout`, `lifestyle-event-scout` |
| `writer` | 文書作成 | （将来の文書作成エージェント用） |
| `planner` | 企画・計画 | `tech-poc-planner` |
| `updater` | データ更新 | `slack-user-directory-updater` |
| `reviewer` | レビュー・検証 | `agent-output-reviewer`, `code-reviewer` |
| `architect` | 設計・構造化 | `spec-architect` |
| `tester` | テスト実行 | `integration-tester` |
| `creator` | 成果物生成 | `slide-creator` |

サブエージェント（親エージェントから委譲される）は親名にサフィックスを付ける:
- `slack-trend-scout-channel`（チャンネル別収集）
- `slack-trend-scout-merge`（統合）
- `gws-trend-scout-collector`（収集フェーズ）
- `gws-trend-scout-aggregator`（集約フェーズ）

#### hookファイル名: `{対象}-{動作名}`

| パターン | 例 | 説明 |
|----------|-----|------|
| `{対象}-{動作}` | `reference-data-refresh` | 参照データの更新 |
| `{対象}-{動作}` | `scouts-weekly-watcher` | 週次scoutの監視 |
| `{対象}-{動作}` | `scouts-daily-trigger` | 日次scoutの起動 |
| `{対象}-{検証名}` | `domain-frontmatter-check` | ドメインファイルのfrontmatter検証 |

#### steeringファイル名: `{トピック}-{文書種別}`

| 文書種別 | 意味 | 例 |
|----------|------|-----|
| `guide` | 手順・ガイド | `agent-creation-guide` |
| `rules` | ルール・制約 | `gws-integration-rules` |
| `base` | 基本方針（グローバル用） | `knowledge-management-base` |
| `patterns` | 設計パターン集 | `agent-prompt-patterns` |
| `mapping` | マッピング・対応表 | `slack-channel-mapping` |

#### スクリプトファイル名: `{動詞}-{対象}`

| 動詞 | 意味 | 例 |
|------|------|-----|
| `find-` | 検索・取得 | `find-task.sh` |
| `update-` | 更新 | `update-task.sh` |
| `create-` | 生成 | `create-weekly-tasks.sh` |
| `fetch-` | 外部取得 | `fetch-rss-feeds.py` |
| `check-` | 検証・判定 | `check-directory-freshness.sh` |

## trend / digest の棲み分け（日次収集 vs 週次集約）

scoutパイプラインは「日次で収集 → 週次で集約」の2層構造を基本とする。

### 設計原則

| 層 | 命名パターン | 実行頻度 | 役割 | API呼び出し |
|---|---|---|---|---|
| 日次収集層 | `{source}-trend-scout` | 毎日 | 対象ソースからデータを直接取得し、日次レポートを出力 | 多い（DB全件クエリ、全文検索、Web検索等） |
| 週次集約層 | `{source}-digest-scout` | 週1回 | 日次レポートを読み込み、統合・分析・追加調査を行う | 最小限（追加調査のみ） |

### 責務の分離

```
[trend-scout] ← 重い処理（API大量呼び出し、データ取得）
  出力: daily/{YYYY-MM-DD}_{source}_daily.md
         ↓ ファイルとして蓄積
[digest-scout] ← 軽い処理（ファイル読み込み + 最小限のAPI追加調査）
  入力: daily/ 配下の直近N日分
  出力: weekly/{YYYY-MM-DD}_{source}_weekly_digest.md
```

### digest-scoutの設計ルール

1. **日次レポートを主入力とする。ソースAPIの全件クエリ・全文検索は使用しない**
2. API呼び出しは「追加調査」のみ（期限超過タスクの最新確認、未決スレッドの最新返信等）
3. API呼び出し数の上限を設ける（目安: 最大10〜15件）
4. 日次レポートで既に解決済みの情報（ユーザー名変換等）は再取得しない
5. 欠損日がある場合はスキップし、レポートに明記する
6. 日次レポートが不足している場合のフォールバック動作を定義する

### 現在の実装

| ソース | 日次（trend） | 週次（digest） | 集約期間 |
|---|---|---|---|
| Slack | `slack-trend-scout` | `slack-digest-scout` | 7日（追跡14日） |
| GWS | `gws-trend-scout` | `gws-digest-scout` | 7日 |
| Notion | `notion-trend-scout` | `notion-digest-scout` | 14日 |

### 新規ソース追加時の判断

1. まず `{source}-trend-scout`（日次収集）を作成し、日次パイプラインに組み込む
2. 日次レポートが十分に蓄積されたら `{source}-digest-scout`（週次集約）を作成
3. digest-scoutは**必ず日次レポートを主入力とする設計**にする（APIを直接叩かない）

## ファイル構成

```
.kiro/agents/
├── {agent-name}.json              # エージェント定義（メタデータ・権限）
├── prompts/
│   ├── {agent-name}.md            # プロンプト本体（~3〜8KB目標）
│   └── pipeline-executor.md       # パイプライン共通実行手順
└── references/
    └── {agent-name}-sources.md    # 収集対象ソース参照（Web検索系のみ）

.kiro/hooks/
└── scouts-{frequency}-watcher.kiro.hook  # パイプラインwatcher
```

## エージェント定義（JSON）

```json
{
  "name": "{agent-name}",
  "description": "{1〜2文の説明}",
  "prompt": "file://./prompts/{agent-name}.md",
  "tools": ["read", "write", "web"],
  "allowedTools": ["web"],
  "toolsSettings": {
    "write": {
      "allowedPaths": ["Documents/works/scout_histories/{output_dir}/**"]
    }
  },
  "resources": [],
  "model": "claude-sonnet-4",
  "welcomeMessage": "{起動時メッセージ}"
}
```

## プロンプト本体の構造（必須セクション）

以下の順序で記載する。**サイズ目標: 3〜8KB**。コンテキスト消費を最小化しつつ必要十分な指示を含める。

### 共通構造（全エージェント）

```markdown
# {Agent Name}（日本語名）

{1文の概要説明}

## 役割
{対象日/対象の何を、どうやって、何を作るか}
対象領域: {カンマ区切りで列挙}

## スコープ
{担当範囲の明示 + 担当外→他エージェント名}

## 対象日付の決定
{日付決定ロジック}

## 収集手順 / 実行手順
{Phase 0〜N の段階的手順}

## 出力
{ファイルパス + フォーマット（ヘッダのみ簡潔に）}

## 行動原則
{番号付き1行ルール。ドメイン固有の判断基準を含む}
```

### Web検索系エージェント追加セクション

```markdown
## 事前取得済み情報（検索不要）
{RSSフィード取得済みソース一覧}
{RSSでカバーできないサイト一覧}

### Phase 0: 重複排除の準備
{過去3日分レポートからURL抽出 → 既出URLリスト作成}
{トップページ・一覧ページは既出リストに含めない}

### Phase 1: 検索・収集
{一時ファイルパス}
{フィルタリングルール: publishedDate / 既出URL / トップページ}
{検索カテゴリ一覧（番号付き、カテゴリ名のみ）}
{書き出しフォーマット指示}

### Phase 2: レポート生成
{feeds + raw_results 統合 → レポート作成 → 一時ファイル削除}
```

### 評価基準セクション（ドメイン固有）

```markdown
## {関連度基準 / 応用可能性基準}
{⭐⭐⭐ / ⭐⭐ / ⭐ の定義}
```

### コンパクト化の原則

`agent-prompt-patterns.md` の「コンパクト化の原則」セクションを参照。

## チェックリスト（新規エージェント作成時）

- [ ] `.kiro/agents/{name}.json` 作成（権限・モデル・書き込み先）
- [ ] `.kiro/agents/prompts/{name}.md` 作成（3〜8KB目標）
- [ ] `.kiro/agents/references/{name}-sources.md` 作成（Web検索系のみ）
- [ ] `scripts/fetch-rss-feeds.py` にカテゴリ追加（RSS取得が必要な場合）
- [ ] `scripts/create-{frequency}-tasks.sh` に子タスク追加（IDE hook方式の場合）
- [ ] `scripts/run-{frequency}-pipeline.sh` の `AGENTS` 配列に追加（kiro-cli方式の場合）
- [ ] `scripts/run-{frequency}-pipeline.sh` の `NOTIFY_FILES` マッピングに追加（Slack通知対象の場合）
- [ ] `.kiro/agents/prompts/pipeline-executor.md` の対象タスクリスト更新（週次モード対象の場合）
- [ ] `.kiro/agents/prompts/pipeline-executor.md` Step 5.1 のSlack通知マッピングに追加（通知対象の場合）
- [ ] `scouts-{frequency}-trigger.kiro.hook` のRSS事前取得ステップに追加（RSS必要な場合）
- [ ] 出力先ディレクトリの存在確認（`Documents/works/scout_histories/{dir}/`）
- [ ] プロンプトサイズ確認（`wc -c` で8KB以下）

## kiro-cli直接実行方式

### 概要

`kiro-cli chat --trust-all-tools --no-interactive` でエージェントをヘッドレス実行する方式。
IDE hookのpostToolUse連鎖に依存せず、シェルスクリプトから直接各エージェントを順次実行する。

### 実行コマンド

```bash
kiro-cli chat --trust-all-tools --no-interactive \
  "{agent-name} エージェントとして動作してください。\`~/.kiro/agents/prompts/{agent-name}.md\` をreadFileで読み込み、そこに記載されたワークフローに従って実行してください。基準日は {BASE_DATE} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

### 制約と注意事項

| 項目 | 内容 |
|------|------|
| MCP環境変数 | `.zshrc` で定義された環境変数をsourceして解決。`kiro-cli` はmcp.jsonの `${...}` をプロセス環境変数から展開する |
| SLACK_BOT_TOKEN | 収集フェーズでは `SLACK_REFERENCE_BOT_TOKEN` を、通知フェーズでは `MY_SLACK_OAUTH_TOKEN` を `SLACK_BOT_TOKEN` にexportして切り替える |
| Notion MCP | SSE接続でブラウザ認証が必要。初回は手動で認証を完了させる。トークンはキャッシュされる |
| ツール承認 | `--trust-all-tools` で全ツールを自動承認。`--no-interactive` と併用必須 |
| セッション独立性 | 各エージェントは独立したセッションで実行される。コンテキスト共有なし |
| 実行完了待ち | ブロッキング動作。エージェント完了までプロセスが待機する |
| Python | `python3.12` を使用（`python3` / `python3.13` は使用禁止） |

### launchd自動実行

```
~/Library/LaunchAgents/com.takeya.scout-daily-pipeline.plist
  → /bin/zsh -l -c ~/scripts/run-daily-pipeline.sh
  → 毎日指定時刻に実行
```

管理コマンド:
```bash
~/scripts/manage-launchd.sh status scout-daily-pipeline
~/scripts/manage-launchd.sh reload scout-daily-pipeline
```

### 日次/週次パイプラインへのエージェント追加

`scripts/run-{frequency}-pipeline.sh` の `AGENTS` 配列に追加:

```bash
# run-daily-pipeline.sh
AGENTS=(
  "tech-trend-scout"
  "biz-car-trend-scout"
  ...
  "{new-agent-name}"  # ← 追加
)

# run-weekly-pipeline.sh
AGENTS=(
  "slack-digest-scout"
  "gws-digest-scout"
  ...
  "{new-agent-name}"  # ← 追加
)
```

Slack通知対象の場合は `NOTIFY_FILES` マッピングにも追加:

```bash
NOTIFY_FILES[{new-agent-name}]="$HOME/Documents/works/scout_histories/{output_dir}/{frequency}/${BASE_DATE}_{output_file}.md"
```

週次パイプラインモード対象の場合は `case` 文にも追加:

```bash
case "$AGENT" in
  tech-event-scout|lifestyle-event-scout|...|{new-agent-name})
    PROMPT="... 「週次パイプラインモード」で ..."
    ;;
esac
```
