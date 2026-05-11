# パイプライン実行スクリプトガイド

`scripts/run-*-pipeline.py` の実装・編集時に遵守すべきルールと参照情報。

## アーキテクチャ

### ファイル構成

```
scripts/
├── _pipeline_common.py              # 共通ユーティリティ + PipelineConfig + run_pipeline()
├── run-daily-pipeline.py            # daily固有の設定 + フック関数
├── run-weekly-pipeline.py           # weekly固有の設定 + フック関数
└── run-gws-trend-scout-pipeline.py  # サブパイプライン（dailyから呼び出し）
```

### 設計方針: 設定dict + 共通runner関数

各パイプラインファイルが `PipelineConfig` を定義し、共通の `run_pipeline()` に渡すフラットな構成。
クラス継承は使わない（スクリプト規模に対して過剰、デバッグしやすさを優先）。

### _pipeline_common.py が提供するもの

| カテゴリ | 内容 |
|---------|------|
| 定数 | `JST`, `HOME`, `SCRIPTS_DIR`, `PLATFORM_CMD`, `MAX_LOG_LINES`, `MAX_AGENT_LOG_LINES` |
| ユーティリティ | `now_jst()`, `rotate_log()`, `load_env()`, `run_kiro_cli()`, `run_sub_pipeline()`, `log_error()` |
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

## サブパイプライン連携

### AGENTSリストでのサブパイプライン指定

`AGENTS` リストに `.py` で終わるエントリを含めると、`run_pipeline()` はそれをサブパイプラインスクリプトとして `run_sub_pipeline()` で実行する。

```python
AGENTS = [
    "tech-trend-scout",              # kiro-cliエージェント
    "run-gws-trend-scout-pipeline.py",  # サブパイプライン
]
```

### ジョブファイル連携（三階層以上）

`run_pipeline()` がサブパイプラインを実行する際、以下の環境変数を自動設定する:

| 環境変数 | 内容 |
|---|---|
| `PIPELINE_JOB_FILE` | ジョブファイルの絶対パス |
| `PIPELINE_PARENT_JOB_ID` | サブパイプライン自身のchild job ID |

サブパイプライン側はこれらを読み込み、内部ステップ（grandchild）の進捗を `update-job.py` で更新する。

### サブパイプライン実装パターン

```python
import os
from pathlib import Path

def load_job_context():
    job_file_str = os.environ.get("PIPELINE_JOB_FILE", "")
    parent_job_id = os.environ.get("PIPELINE_PARENT_JOB_ID", "")
    job_file = Path(job_file_str) if job_file_str and Path(job_file_str).exists() else None
    return job_file, parent_job_id

# 単独実行時（環境変数なし）はジョブ管理をスキップ
job_file, parent_job_id = load_job_context()
if job_file:
    # grandchildジョブを更新
    subprocess.run(["python3.12", "scripts/update-job.py",
                    "--job-file", str(job_file),
                    "--job-id", grandchild_id,
                    "--set", '{"status": "running"}'])
```

### create-*-jobs.py でのgrandchild定義

サブパイプラインのジョブ定義に `child_jobs` を含めることで、grandchildジョブが自動生成される:

```python
CHILD_JOBS = [
    {"job_name": "run-gws-trend-scout-pipeline", "timeout": 900, "child_jobs": [
        {"job_name": "gws-extractor-docs", "timeout": 300},
        {"job_name": "gws-extractor-slides", "timeout": 300},
    ]},
]
```

詳細は `job-management-guide.md` を参照。

## 制約と注意事項

| 項目 | 内容 |
|------|------|
| --agent フラグ | 必ず `--agent {agent-name}` を指定。エージェント定義の `prompt`, `tools`, `includeMcpJson`, `model` が自動適用される |
| MCP環境変数 | `.zshrc` で定義された環境変数をsourceして解決。`kiro-cli` はmcp.jsonの `${...}` をプロセス環境変数から展開する |
| SLACK_BOT_TOKEN | 収集フェーズ: `SLACK_REFERENCE_BOT_TOKEN` / 通知フェーズ: `MY_SLACK_OAUTH_TOKEN` を切り替え |
| Notion MCP | SSE接続でブラウザ認証が必要。初回は手動認証。`includeMcpJson: false` のエージェントではロードされない |
| ツール承認 | `--trust-all-tools` で全ツールを自動承認。`--no-interactive` と併用必須 |
| セッション独立性 | 各エージェントは独立したセッションで実行。コンテキスト共有なし |
| 実行完了待ち | ブロッキング動作。エージェント完了までプロセスが待機する |
| Python | `python3.12` を使用（`python3` / `python3.13` は使用禁止） |

## エージェント実行プロンプト

`build_prompt` コールバックで構築する。基本形:

```python
f"基準日は {base_date} です。日付をシェルコマンドで取得する代わりに、この基準日を使用してください。"
```

週次パイプラインモード対象の場合は先頭に `「週次パイプラインモード」で実行してください。` を付加。

`--agent` によりエージェント定義の `prompt`（`file://...`）が自動ロードされるため、プロンプト内でのロール宣言やreadFile指示は不要。パラメータ（基準日、ファイルパス等）のみ渡す。

## スケジューラ管理

`launchctl` / `systemctl` の直接使用は禁止。必ず `manage-scheduler.py` を経由する:

```bash
python3.12 ~/scripts/manage-scheduler.py {load|unload|reload|status|list} {label}
```

理由: プラットフォーム差異の吸収 + 将来のクラウドスケジューラ移行に備えた抽象化。

自動実行: `~/Library/LaunchAgents/com.takeya.{pipeline-name}.plist`

## ログ構造

```
~/logs/jobs/{pipeline名}/
  ├── pipeline.log          # パイプライン全体ログ
  ├── pipeline-error.log    # エラーログ（launchd StandardErrorPath）
  ├── {agent-name}.log      # 各エージェント個別ログ
  ├── slack-notify.log      # Slack通知ログ
  └── reference-refresh.log # 参照データ更新ログ（週次のみ）
```

ログローテーション: 行数ベース（パイプライン: 1000行/keep200、エージェント: 500行/keep100）

## ジョブ管理

| 操作 | コマンド |
|------|---------|
| ジョブ検索 | `python3.12 ~/scripts/find-job.py` |
| ジョブ更新 | `python3.12 ~/scripts/update-job.py` |
| ジョブ生成 | `python3.12 ~/scripts/create-jobs.py` |

ジョブファイルのパスを直接ハードコードしない。`find-job.py` で動的に取得する。

## Slack通知

`NOTIFY_FILE_MAP` でエージェント名→出力ファイルテンプレートを定義。`run_pipeline()` が各ファイルにつき1回 `slack-notifier` エージェントを呼び出す（セッション独立、前のファイル内容は保持しない）。

- マッピングに無いエージェント → スキップ
- 出力ファイルが存在しない → スキップ
- 動的パス解決が必要 → `resolve_notify_path` コールバックで対応

## 依存関係の解決

`AGENTS` 配列の順序で順次実行。依存関係は配列の並び順で暗黙的に解決する。
`depends_on` 付きジョブは、依存先が先に実行されるよう配置する。
