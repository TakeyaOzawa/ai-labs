# Scout パイプライン統合ガイド

パイプラインへのエージェント組み込み、hook連携、低頻度更新データの設計パターン。
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

### タスク生成スクリプトへの追加

`scripts/create-{frequency}-tasks.sh` に子タスクを追加:

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
| `scripts/check-directory-freshness.sh` | 最終更新日からの経過日数で鮮度判定 | `--type slack --max-age-days 7` |
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
  → check-directory-freshness.sh で鮮度チェック
  → stale なら invokeSubAgent で更新実行
```

### 鮮度チェックの設計

```bash
~/scripts/check-directory-freshness.sh --type {type} --max-age-days {N}
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
- [ ] `check-directory-freshness.sh` の `--type` に対応追加（必要な場合）
- [ ] 更新エージェント（JSON + プロンプト）作成
- [ ] 手動トリガーhook作成（`userTriggered`）
- [ ] `reference-data-refresh.kiro.hook` のStep 1に鮮度チェックコマンド追加
- [ ] `reference-data-refresh.kiro.hook` のStep 2にinvokeSubAgent追加
- [ ] steeringのlookupガイド作成（他エージェントからの参照方法を定義）
