# パイプライン実行スクリプトガイド

`scripts/run-*-pipeline.py` の実装・編集時に遵守すべきルールと参照情報。

## 実行コマンド（kiro-cli）

```bash
kiro-cli chat --trust-all-tools --no-interactive \
  "{agent-name} エージェントとして動作してください。\`~/.shared-ai/prompts/{agent-name}.md\` をreadFileで読み込み、そこに記載されたワークフローに従って実行してください。基準日は {BASE_DATE} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

週次パイプラインモード対象の場合:
```bash
"{agent-name} エージェントとして「週次パイプラインモード」で動作してください。..."
```

## 制約と注意事項

| 項目 | 内容 |
|------|------|
| MCP環境変数 | `.zshrc` で定義された環境変数をsourceして解決。`kiro-cli` はmcp.jsonの `${...}` をプロセス環境変数から展開する |
| SLACK_BOT_TOKEN | 収集フェーズでは `SLACK_REFERENCE_BOT_TOKEN` を、通知フェーズでは `MY_SLACK_OAUTH_TOKEN` を `SLACK_BOT_TOKEN` にexportして切り替える |
| Notion MCP | SSE接続でブラウザ認証が必要。初回は手動で認証を完了させる。トークンはキャッシュされる |
| ツール承認 | `--trust-all-tools` で全ツールを自動承認。`--no-interactive` と併用必須 |
| セッション独立性 | 各エージェントは独立したセッションで実行される。コンテキスト共有なし |
| 実行完了待ち | ブロッキング動作。エージェント完了までプロセスが待機する |
| Python | `python3.12` を使用（`python3` / `python3.13` は使用禁止） |

## スケジューラ管理

### 禁止事項

- `launchctl` を直接使用しないこと
- `systemctl` を直接使用しないこと

### 正しい方法

スケジュールの登録・解除・確認は必ず `manage-scheduler.py` を経由する:

```bash
python3.12 ~/scripts/manage-scheduler.py load {label}
python3.12 ~/scripts/manage-scheduler.py unload {label}
python3.12 ~/scripts/manage-scheduler.py reload {label}
python3.12 ~/scripts/manage-scheduler.py status {label}
python3.12 ~/scripts/manage-scheduler.py list
```

理由:
- プラットフォーム差異（macOS: launchd / Linux: systemd）を吸収する
- 将来のクラウドスケジューラ移行に備えた抽象化

### 自動実行の設定

```
~/Library/LaunchAgents/com.takeya.{pipeline-name}.plist
  → python3.12 ~/scripts/run-{name}-pipeline.py
```

## ログ構造

```
~/logs/jobs/{pipeline名}/
  ├── pipeline.log          # パイプライン全体ログ
  ├── pipeline-error.log    # エラーログ（launchd StandardErrorPath）
  ├── {agent-name}.log      # 各エージェント個別ログ
  ├── slack-notify.log      # Slack通知ログ
  └── reference-refresh.log # 参照データ更新ログ（週次のみ）
```

新規パイプライン作成時も同じ構造に従う: `~/logs/jobs/{pipeline名}/`

### ログローテーション

- パイプライン全体ログ: MAX_LOG_LINES=1000, keep_lines=200
- 各エージェントログ: MAX_AGENT_LOG_LINES=500, keep_lines=100
- 方式: 行数ベース（末尾N行を残して切り詰め）

## ジョブ管理

ジョブファイルの操作は抽象化スクリプトを使用する:

| 操作 | コマンド |
|------|---------|
| ジョブ検索 | `python3.12 ~/scripts/find-job.py` |
| ジョブ更新 | `python3.12 ~/scripts/update-job.py` |
| ジョブ生成 | `python3.12 ~/scripts/create-jobs.py` |

ジョブファイルのパスを直接ハードコードしない。`find-job.py` で動的に取得する。

## 環境変数

| フェーズ | SLACK_BOT_TOKEN の値 |
|----------|---------------------|
| 収集フェーズ | `SLACK_REFERENCE_BOT_TOKEN` |
| 通知フェーズ | `MY_SLACK_OAUTH_TOKEN` |

切り替えは `os.environ["SLACK_BOT_TOKEN"] = os.environ.get("...", "")` で行う。

## エージェント実行プロンプトの構築

### 基本形

```python
prompt = (
    f"{agent} エージェントとして動作してください。"
    f" ~/.shared-ai/prompts/{agent}.md をreadFileで読み込み、"
    f"そこに記載されたワークフローに従って実行してください。"
    f"基準日は {base_date} です。"
    f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
)
```

### 週次パイプラインモード対象の場合

```python
prompt = (
    f"{agent} エージェントとして「週次パイプラインモード」で動作してください。"
    f" ~/.shared-ai/prompts/{agent}.md をreadFileで読み込み、"
    f"そこに記載された週次パイプラインモードのワークフローに従って実行してください。"
    f"基準日は {base_date} です。"
    f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
)
```

## 失敗時のリトライコマンド表示

エージェント実行が失敗した場合、ユーザーが手動で再実行できるよう kiro-cli コマンドを表示する:

```python
print(f"[{agent_end}]    💡 再実行: kiro-cli chat --trust-all-tools --no-interactive \"{prompt}\"")
```

- ❌ 行の直後に出力する
- プロンプト文字列はそのまま埋め込む（コピー&ペーストで即実行可能にする）

## Slack通知の設計

### 通知対象ファイルマッピング

`NOTIFY_FILE_MAP` dict でエージェント名→出力ファイルパスを定義する:

```python
NOTIFY_FILE_MAP = {
    "agent-name": "scout_histories/{dir}/{frequency}/{date}_{file}.md",
}
```

- マッピングに無いエージェントは通知スキップ
- 出力ファイルが存在しない場合もスキップ
- failedのジョブは通知スキップ

### 通知実行

各ファイルについて `slack-notifier` エージェントを kiro-cli で呼び出す。
1ファイル1呼び出しで、前のファイル内容を保持する必要がない。

## 依存関係の解決

### kiro-cli経路（run-*-pipeline.py）

`AGENTS` 配列の順序で順次実行する。依存関係は配列の並び順で暗黙的に解決される。
`depends_on` 付きジョブは、依存先が `AGENTS` 配列で先に実行されるよう配置する。

### IDE経路（将来再実装する場合）

`depends_on` フィールドを使い、完了したジョブの `job_name` と一致する `depends_on` を持つ pending ジョブを `starting` に遷移させる。1回のhook発火で1ジョブのみ処理し、再発火トリガー（ジョブファイルへの書き込み）で連鎖実行する。
