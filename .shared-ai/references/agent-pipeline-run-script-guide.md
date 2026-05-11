# パイプライン実行スクリプトガイド

`scripts/run-*-pipeline.py` の実装・編集時に遵守すべきルールと参照情報。

## アーキテクチャ

### ファイル構成

```
scripts/
├── _pipeline_common.py         # 共通ユーティリティ + PipelineConfig + run_pipeline()
├── run-daily-pipeline.py       # daily固有の設定 + フック関数
└── run-weekly-pipeline.py      # weekly固有の設定 + フック関数
```

### 設計方針: 設定dict + 共通runner関数

各パイプラインファイルが `PipelineConfig` を定義し、共通の `run_pipeline()` に渡すフラットな構成。
クラス継承は使わない（スクリプト規模に対して過剰、デバッグしやすさを優先）。

### _pipeline_common.py が提供するもの

| カテゴリ | 内容 |
|---------|------|
| 定数 | `JST`, `HOME`, `SCRIPTS_DIR`, `PLATFORM_CMD`, `MAX_LOG_LINES`, `MAX_AGENT_LOG_LINES` |
| ユーティリティ | `now_jst()`, `rotate_log()`, `load_env()`, `run_kiro_cli()`, `log_error()` |
| ヘルパー | `start_caffeinate()`, `stop_caffeinate()`, `get_child_job_id()`, `update_job()` |
| 設定クラス | `PipelineConfig` dataclass |
| runner | `run_pipeline(config)` — パイプライン共通実行フロー |

### PipelineConfig フィールド

```python
@dataclass
class PipelineConfig:
    name: str                          # "daily" | "weekly"
    log_dir: Path                      # ログ出力ディレクトリ
    agents: list[str]                  # エージェントリスト
    notify_file_map: dict[str, str]    # エージェント名 → 通知ファイルテンプレート
    create_jobs_script: str            # ジョブファイル生成スクリプト名
    default_base_date: Callable[[], str]  # 基準日デフォルト計算

    # 以下はオプション（デフォルト: None or デフォルト関数）
    rss_fetch_hook: Callable[[str, Path], None] | None          # RSS取得ステップ全体
    build_prompt: Callable[[str, str], str]                      # (agent, base_date) -> prompt
    resolve_notify_path: Callable[[str, str], Path | None] | None  # 通知ファイルパス動的解決
    pre_agent_hook: Callable[[str, str], str | None] | None     # スキップ判定
    post_agents_hook: Callable[[str], None] | None              # 全エージェント実行後
    post_notify_hook: Callable[[str], None] | None              # 通知後の追加ステップ
```

### run_pipeline() の実行フロー

1. オプション解析（`--no-job-file`, 基準日）
2. 環境準備（caffeinate, load_env, SLACK_BOT_TOKEN設定）
3. ログローテーション
4. Step 0: ジョブファイル生成
5. Step 1: `rss_fetch_hook` によるRSSフィード事前取得
6. Step 2: エージェント実行ループ（`pre_agent_hook` → `build_prompt` → `run_kiro_cli`）
7. Step 2.5: `post_agents_hook`
8. Step 3: 親タスク完了処理
9. Step 4: Slack通知（`resolve_notify_path` → `slack-notifier`）
10. Step 5: `post_notify_hook`
11. Step 6: 完了サマリー + caffeinate解除

### 新規パイプライン作成テンプレート

```python
#!/usr/bin/env python3.12
from pathlib import Path

from _pipeline_common import HOME, JST, PipelineConfig, run_pipeline

LOG_DIR = HOME / "logs" / "jobs" / "scout_{name}"
AGENTS = [...]
NOTIFY_FILE_MAP = {...}

def _default_base_date() -> str: ...
def _rss_fetch_hook(base_date: str, scripts_dir: Path) -> None: ...
def _build_prompt(agent: str, base_date: str) -> str: ...

def main() -> None:
    config = PipelineConfig(
        name="{name}",
        log_dir=LOG_DIR,
        agents=AGENTS,
        notify_file_map=NOTIFY_FILE_MAP,
        create_jobs_script="create-{name}-jobs.py",
        default_base_date=_default_base_date,
        rss_fetch_hook=_rss_fetch_hook,
        build_prompt=_build_prompt,
    )
    run_pipeline(config)

from _version_check import check_python_version
if __name__ == "__main__":
    check_python_version()
    main()
```

## 実行コマンド（kiro-cli）

```bash
kiro-cli chat --agent {agent-name} --trust-all-tools --no-interactive \
  "基準日は {BASE_DATE} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

週次パイプラインモード対象の場合:
```bash
kiro-cli chat --agent {agent-name} --trust-all-tools --no-interactive \
  "「週次パイプラインモード」で実行してください。基準日は {BASE_DATE} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

`--agent` フラグにより、エージェント定義（`.kiro/agents/{agent-name}.json`）の以下が自動適用される:
- `prompt`: プロンプトファイル（`file://...`）の自動ロード
- `tools` / `allowedTools`: ツール制限
- `includeMcpJson`: MCPサーバーのロード制御
- `model`: 使用モデル

## 制約と注意事項

| 項目 | 内容 |
|------|------|
| --agent フラグ | 必ず `--agent {agent-name}` を指定する。エージェント定義（`.kiro/agents/{name}.json`）の `prompt`, `tools`, `includeMcpJson`, `model` が自動適用される |
| MCP環境変数 | `.zshrc` で定義された環境変数をsourceして解決。`kiro-cli` はmcp.jsonの `${...}` をプロセス環境変数から展開する |
| SLACK_BOT_TOKEN | 収集フェーズでは `SLACK_REFERENCE_BOT_TOKEN` を、通知フェーズでは `MY_SLACK_OAUTH_TOKEN` を `SLACK_BOT_TOKEN` にexportして切り替える |
| Notion MCP | SSE接続でブラウザ認証が必要。初回は手動で認証を完了させる。トークンはキャッシュされる。`includeMcpJson: false` のエージェントではMCPサーバーはロードされない |
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
    f"基準日は {base_date} です。"
    f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
)
```

### 週次パイプラインモード対象の場合

```python
prompt = (
    f"「週次パイプラインモード」で実行してください。"
    f"基準日は {base_date} です。"
    f"日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
)
```

### run_kiro_cli 呼び出し

```python
run_kiro_cli(prompt, agent_log, agent_name=agent)
```

`--agent` によりエージェント定義の `prompt` フィールド（`file://...`）が自動ロードされるため、
プロンプト内でのロール宣言やreadFile指示は不要。パラメータ（基準日、ファイルパス等）のみ渡す。

## 失敗時のリトライコマンド表示

エージェント実行が失敗した場合、ユーザーが手動で再実行できるよう kiro-cli コマンドを表示する:

```python
print(f"[{agent_end}]    💡 再実行: kiro-cli chat --agent {agent} --trust-all-tools --no-interactive \"{prompt}\"")
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
