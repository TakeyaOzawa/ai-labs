# パイプライン統合ガイド

エージェントのパイプラインへの組み込み、低頻度更新データの設計指針。

## パイプラインへの組み込み

### エージェント追加手順（kiro-cli方式）

`kiro-cli chat --trust-all-tools --no-interactive` でエージェントをヘッドレス実行する方式。
`scripts/run-{frequency}-pipeline.py` から直接各エージェントを順次実行する。

#### 1. ジョブ生成スクリプトへの追加

**既存パイプライン（daily/weekly）に追加する場合:**

`scripts/create-{frequency}-jobs.py` の `CHILD_TASKS` に子ジョブ定義を追加:

```python
{"job_name": "{agent-name}", "timeout": 300, "retry_delay": 30, "depends_on": None},
```

**新規パイプラインの場合:**

汎用 `scripts/create-jobs.py` を使用:

```bash
python3.12 ~/scripts/create-jobs.py \
  --pipeline {pipeline_name} \
  --base-date {YYYY-MM-DD} \
  --jobs-file /path/to/tasks-def.json
```

または `--jobs` でインライン指定:
```bash
python3.12 ~/scripts/create-jobs.py \
  --pipeline {pipeline_name} \
  --base-date {YYYY-MM-DD} \
  --jobs '[{"job_name": "{agent-name}", "timeout": 300, "retry_delay": 30, "depends_on": null}]'
```

- `depends_on`: 他タスクの完了を待つ場合はそのタスク名を指定（例: `"tech-blog-material-scout"`）
- `timeout`: Web検索系は300〜600、API系は600〜900が目安

#### 2. パイプラインスクリプトへの追加

`scripts/run-{frequency}-pipeline.py` の `AGENTS` リストに追加:

```python
AGENTS = [
    ...
    "{new-agent-name}",  # ← 追加
]
```

週次パイプラインモード対象の場合は `WEEKLY_PIPELINE_MODE_AGENTS` にも追加:

```python
WEEKLY_PIPELINE_MODE_AGENTS = {
    ...
    "{new-agent-name}",  # ← 追加
}
```

#### 3. Slack通知対象の場合

`NOTIFY_FILE_MAP` にマッピングを追加:

```python
NOTIFY_FILE_MAP = {
    ...
    "{new-agent-name}": "scout_histories/{output_dir}/{frequency}/{date}_{output_file}.md",
}
```

#### 4. RSS事前取得が必要な場合

- `scripts/fetch-rss-feeds.py` の `FEEDS` にカテゴリ追加
- `run-{frequency}-pipeline.py` のStep 1にカテゴリ追加

#### 実行スクリプトの実装ルール

実行コマンド、制約事項、ログ構造、スケジューラ管理については `~/.shared-ai/references/agent-pipeline-run-script-guide.md` を参照。

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

> **Note**: 週次パイプライン完了後の鮮度チェック・自動更新は `run-weekly-pipeline.py` の Step 5 で実行される。

### 自動更新hookの発火条件

```
週次scoutパイプライン完了
  → `run-weekly-pipeline.py` の Step 3 で親タスクを completed に更新
  → `run-weekly-pipeline.py` の Step 5 で鮮度チェック・更新を実行
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
- [ ] `run-weekly-pipeline.py` の `run_freshness_check()` に鮮度チェック対象を追加
- [ ] `run-weekly-pipeline.py` の `run_freshness_check()` に更新プロンプトを追加
- [ ] steeringのlookupガイド作成（他エージェントからの参照方法を定義）
