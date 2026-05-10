# パイプライン統合ガイド

エージェントのパイプラインへの組み込み、hook連携、低頻度更新データの設計指針。
`pipeline-executor.md` やwatcher hookを読み込んだ際に自動ロードされる。

## hook連携の設計

### watcher hookの構造（軽量版）

```json
{
  "when": { "type": "postToolUse", "toolTypes": ["write"] },
  "then": {
    "type": "askAgent",
    "prompt": "直前のwrite操作が{対象}への書き込みか判定し、該当する場合のみ処理を実行。\n\n## Step 0: 対象ファイル判定\n\n- パスが `{対象ディレクトリ}` 配下の `.json` ファイル **でない** 場合 → 何もせず終了\n- 該当する場合 → `.shared-ai/prompts/pipeline-executor.md` をreadFileで読み込み、`{pipeline}` を `{frequency}` として手順に従い実行してください。"
  }
}
```

### 設計ポイント
- hookのプロンプトは**ファイル判定 + executor参照**の最小形（~300B）
- 詳細な実行手順は `pipeline-executor.md` に集約（DRY原則）
- 対象外のwrite操作では即座に終了（コンテキスト消費を最小化）

### pipeline-executor.md への追加

新しいパイプラインを追加する場合:
1. `pipeline-executor.md` の「週次パイプラインモード対象タスク」リストに追加
2. 「その他のタスク」として扱うか、「週次パイプラインモード」として扱うかを決定
3. 週次パイプラインモード = プロンプトに「## 週次パイプラインモード」セクションがあるタスク

## パイプラインへの組み込み

### IDE hook方式

#### タスク生成スクリプトへの追加

`scripts/create-{frequency}-tasks.py` に子タスクを追加:

```json
{
  "task_id": "${CHILD_IDS[N]}",
  "task_name": "{agent-name}",
  "args": { "base_date": "${BASE_DATE}" },
  "options": { "async": true, "timeout_seconds": 300, "max_retries": 1, "retry_delay_seconds": 30 },
  "status": "starting",
  "depends_on": null,
  "child_tasks": []
}
```

- `depends_on`: 他タスクの完了を待つ場合はそのタスク名を指定
- `status`: `depends_on` が null なら `"starting"`、null でなければ `"pending"`
- `timeout_seconds`: Web検索系は300〜600、API系は600〜900が目安

#### その他のIDE hook方式更新

1. `pipeline-executor.md` の対象タスクリスト更新（週次パイプラインモード対象の場合）
2. `pipeline-executor.md` Step 5.1 のSlack通知マッピングテーブルに追加（通知対象の場合）
3. RSS事前取得が必要なら:
   - `scripts/fetch-rss-feeds.py` にカテゴリ追加
   - `scouts-{frequency}-trigger.kiro.hook` のRSS事前取得ステップに追加

### kiro-cli シェルスクリプト方式

`kiro-cli chat --trust-all-tools --no-interactive` でエージェントをヘッドレス実行する方式。
IDE hookのpostToolUse連鎖に依存せず、シェルスクリプトから直接各エージェントを順次実行する。

#### 実行コマンド

```bash
kiro-cli chat --trust-all-tools --no-interactive \
  "{agent-name} エージェントとして動作してください。\`~/.shared-ai/prompts/{agent-name}.md\` をreadFileで読み込み、そこに記載されたワークフローに従って実行してください。基準日は {BASE_DATE} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

#### 環境変数の設定

```bash
# .zshrc からsource（未設定時のみ）
if [[ -z "${MY_SLACK_OAUTH_TOKEN:-}" ]]; then
  [[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc" 2>/dev/null || true
fi

# MCPサーバーが直接参照する環境変数をexport
export SLACK_BOT_TOKEN="${SLACK_REFERENCE_BOT_TOKEN:-}"  # 収集フェーズ
export SLACK_TEAM_ID="${SLACK_REFERENCE_TEAM_ID:-}"

# 通知フェーズ前に切り替え
export SLACK_BOT_TOKEN="${MY_SLACK_OAUTH_TOKEN:-}"  # 通知フェーズ
```

#### エージェント追加手順

`scripts/run-{frequency}-pipeline.py` の `AGENTS` 配列に追加:

```bash
AGENTS=(
  "tech-trend-scout"
  "biz-car-trend-scout"
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

#### 制約と注意事項

| 項目 | 内容 |
|------|------|
| MCP環境変数 | `.zshrc` で定義された環境変数をsourceして解決。`kiro-cli` はmcp.jsonの `${...}` をプロセス環境変数から展開する |
| SLACK_BOT_TOKEN | 収集フェーズでは `SLACK_REFERENCE_BOT_TOKEN` を、通知フェーズでは `MY_SLACK_OAUTH_TOKEN` を `SLACK_BOT_TOKEN` にexportして切り替える |
| Notion MCP | SSE接続でブラウザ認証が必要。初回は手動で認証を完了させる。トークンはキャッシュされる |
| ツール承認 | `--trust-all-tools` で全ツールを自動承認。`--no-interactive` と併用必須 |
| セッション独立性 | 各エージェントは独立したセッションで実行される。コンテキスト共有なし |
| 実行完了待ち | ブロッキング動作。エージェント完了までプロセスが待機する |
| Python | `python3.12` を使用（`python3` / `python3.13` は使用禁止） |

#### launchd自動実行

```
~/Library/LaunchAgents/com.takeya.scout-daily-pipeline.plist
  → python3.12 ~/scripts/run-daily-pipeline.py
  → 毎日指定時刻に実行
```

管理コマンド:
```bash
python3.12 ~/scripts/manage-launchd.py status scout-daily-pipeline
python3.12 ~/scripts/manage-launchd.py reload scout-daily-pipeline
```

## 低頻度更新データの事前取得エージェント設計

### 判断基準: 別途カスタムエージェントを組むべきケース

メイン処理の前に取得が必要だが、更新頻度が低いデータは**独立したエージェント + 自動鮮度チェック**で管理する。

| 判断基準 | 該当する場合 | 例 |
|----------|-------------|-----|
| 更新頻度がメイン処理より低い | 週1〜月1回で十分 | ユーザー一覧、組織図、チャンネルマッピング |
| メイン処理の事前条件である | これがないとメイン処理の品質が下がる | ユーザーID→名前変換 |
| 取得コストが高い | API呼び出し多数、レートリミットあり | Slack全ユーザー取得 |
| 取得結果が複数エージェントで共有される | 1回取得すれば複数scoutが参照 | Notionユーザー |
| メイン処理のコンテキストを圧迫する | 取得処理自体が重い | 全ユーザー分類+ファイル出力 |

### 設計パターン

```
[鮮度チェックスクリプト] → stale判定
       ↓ stale: true
[更新エージェント] → データ取得+ファイル出力
       ↓
[メイン処理エージェント] → 出力ファイルをreadFileで参照
```

### 実装構成

| コンポーネント | 役割 | 例 |
|---|---|---|
| `scripts/check-directory-freshness.py` | 最終更新日からの経過日数で鮮度判定 | `--type slack --max-age-days 7` |
| `.kiro/agents/{name}-updater.json` | 更新エージェント定義 | `slack-user-directory-updater` |
| `.shared-ai/prompts/{name}-updater.md` | 更新手順プロンプト | API呼び出し→分類→ファイル出力 |
| `.kiro/hooks/{name}-update.kiro.hook` | 手動トリガー（`userTriggered`） | 任意のタイミングで手動実行 |
| `.kiro/hooks/reference-data-refresh.kiro.hook` | 自動トリガー（パイプライン完了後） | 週次scout完了時に鮮度チェック→必要なら更新 |

### 自動更新hookの発火条件

```
週次scoutパイプライン完了
  → pipeline-executor.md の完了マーカーで strReplace 発火
  → postToolUse(write) hook が発火
  → reference-data-refresh hook が検知
  → 親タスク status == "completed" を確認
  → check-directory-freshness.py で鮮度チェック
  → stale なら invokeSubAgent で更新実行
```

### 鮮度チェックの設計

```bash
python3.12 ~/scripts/check-directory-freshness.py --type {type} --max-age-days {N}
# 出力: {"stale": true/false, "type": "...", "last_updated": "YYYY-MM-DD", "age_days": N}
```

- 最終更新日は「日付ディレクトリ名」から判定（ファイルのmtimeではない）
- ディレクトリが存在しない場合は `stale: true`（初回実行が必要）
- `max-age-days` はデータの性質に応じて設定:
  - ユーザー一覧: 7〜14日（人事異動・入退社の反映）
  - チャンネルマッピング: 30日（チャンネル構成は頻繁に変わらない）
  - 組織図: 30〜90日（四半期ごとの組織変更）

### 現在の実装例

| データ | エージェント | 更新頻度 | 自動トリガー | 手動トリガー |
|--------|-------------|----------|-------------|-------------|
| Slackユーザー一覧 | `slack-user-directory-updater` | 7日 | 週次scout完了後 | `slack-user-directory-update` hook |
| Notionユーザー一覧 | `notion-user-directory-updater` | 14日 | 週次scout完了後 | `notion-user-directory-update` hook |

### 新規追加時のチェックリスト

- [ ] 更新頻度の決定（`max-age-days`）
- [ ] `check-directory-freshness.py` の `--type` に対応追加（必要な場合）
- [ ] 更新エージェント（JSON + プロンプト）作成
- [ ] 手動トリガーhook作成（`userTriggered`）
- [ ] `reference-data-refresh.kiro.hook` のStep 1に鮮度チェックコマンド追加
- [ ] `reference-data-refresh.kiro.hook` のStep 2にinvokeSubAgent追加
- [ ] steeringのlookupガイド作成（他エージェントからの参照方法を定義）
