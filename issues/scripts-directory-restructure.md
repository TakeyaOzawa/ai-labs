# scripts-directory-restructure: scriptsディレクトリの階層構造整理・モジュール化・テスト基盤構築

## 変更種別

refactor

## 概要

- `~/scripts/` 配下の50+スクリプトをドメイン別サブディレクトリに整理する
- フラット構造から階層構造に移行し、見通しと保守性を改善する
- スクリプトのクラス化・モジュール化を推進し、再利用性とテスタビリティを向上させる
- pytest + coverage による単体テスト・結合テストの基盤を構築する
- pyproject.toml による統一的なプロジェクト設定と自動テスト機構を導入する

## 問題・背景

- 現在55ファイルがフラットに配置されており、目的のスクリプトを見つけにくい
- 機能的に関連するスクリプト群（Slack連携、GWS連携、パイプライン等）が混在している
- スクリプト追加のたびに一覧が肥大化し、READMEの主要スクリプト表も長大になっている
- テストが2ファイルのみで、独自のassertユーティリティを使用しており、pytestエコシステムの恩恵を受けられていない
- ビジネスロジックがスクリプトの `if __name__ == "__main__"` ブロック内に直接記述されており、単体テストが困難
- 共通処理（Slack通知、ジョブ管理、ファイルI/O等）が各スクリプトに散在し、重複コードが存在する

## 新しいディレクトリ構造

```
scripts/
├── pyproject.toml                # プロジェクト設定（pytest, ruff, coverage）
├── README.md
├── platform-commands.sh          # シェルユーティリティ（パス参照が広範なためルートに残す）
├── conftest.py                   # pytest共通fixture
│
├── lib/                          # 共通ライブラリ（Pythonパッケージ）
│   ├── __init__.py
│   ├── pipeline_common.py        # 旧 _pipeline_common.py（クラス化済み）
│   ├── version_check.py          # 旧 _version_check.py
│   ├── logger.py                 # 旧 logger.py
│   ├── slack_client.py           # Slack API操作の共通クラス
│   ├── gws_client.py             # GWS API操作の共通クラス
│   ├── job_manager.py            # ジョブ管理ロジック（クラス化）
│   └── config.py                 # 環境変数・パス定数の一元管理
│
├── pipelines/                    # パイプライン実行エントリポイント
│   ├── run-daily-pipeline.py
│   ├── run-weekly-pipeline.py
│   ├── run-freshness-pipeline.py
│   ├── run-poc-planner-pipeline.py
│   ├── run-gws-trend-scout-pipeline.py
│   ├── run-academic-trend-scout-pipeline.py
│   ├── run-github-org-trend-scout-pipeline.py
│   └── run-github-repo-analysis-pipeline.py
│
├── jobs/                         # ジョブ管理（CRUD + スケジューラ）
│   ├── find-job.py
│   ├── update-job.py
│   ├── create-jobs.py
│   ├── create-daily-jobs.py
│   ├── create-weekly-jobs.py
│   ├── manage-scheduler.py
│   └── manage-wake-schedule.py
│
├── slack/                        # Slack連携
│   ├── run-slack-dispatch-router.py
│   ├── dispatch-agent-wrapper.py
│   ├── notify-slack.py
│   ├── fetch-slack-users.py
│   ├── update-slack-user-directory.py
│   └── slack-channel-collector.py
│
├── gws/                          # Google Workspace連携
│   ├── extract-gws-doc-text.py
│   ├── extract-gws-sheets-header.py
│   ├── extract-gws-slides-text.py
│   ├── filter-gws-drive-metadata.py
│   ├── merge-gws-intermediate-files.py
│   └── summarize-filtered-metadata.py
│
├── data/                         # データ加工・変換
│   ├── filter-contact-history-csv.py
│   ├── filter-customer-csv.py
│   ├── mask-private-csv.py
│   ├── generate-negotiation-records-sql.py
│   └── extract-repo-analysis-data.py
│
├── rss/                          # RSS/学術フィード
│   ├── fetch-rss-feeds.py
│   ├── rss-source-updater.py
│   ├── split-academic-feeds.py
│   └── merge-academic-intermediate-files.py
│
├── ai/                           # AI/エージェント関連
│   ├── ai-cli-utils.py
│   ├── invoke-agent.py
│   ├── resolve-shared-ai-rules.py
│   └── sync-claude-agents.py
│
├── setup/                        # セットアップ・検証
│   ├── setup-shared-ai.py
│   ├── setup-symlinks.py
│   ├── verify-shared-ai-structure.py
│   ├── check-env.py
│   ├── check-directory-freshness.py
│   └── audit-documentation.py
│
├── utils/                        # 汎用ユーティリティ
│   ├── decode-b64-write.py
│   ├── encode-to-b64.py
│   ├── epoch-to-jst.py
│   ├── get-jst-date.py
│   └── free-notion-mcp-port.py
│
├── tests/                        # テストディレクトリ（pytest準拠）
│   ├── conftest.py               # テスト共通fixture・ヘルパー
│   ├── unit/                     # 単体テスト
│   │   ├── __init__.py
│   │   ├── test_pipeline_common.py
│   │   ├── test_logger.py
│   │   ├── test_slack_client.py
│   │   ├── test_gws_client.py
│   │   ├── test_job_manager.py
│   │   ├── test_config.py
│   │   ├── test_dispatch_report_path.py  # 既存テスト移行
│   │   └── test_rss_source_updater.py    # 既存テスト移行
│   └── integration/              # 結合テスト
│       ├── __init__.py
│       ├── test_pipeline_execution.py
│       ├── test_slack_dispatch_flow.py
│       ├── test_job_lifecycle.py
│       └── test_gws_pipeline.py
│
├── git-hooks/                    # 既存のまま
│   └── pre-commit
│
└── old/                          # 既存のまま
```

## 分類基準

| ディレクトリ | 分類基準 |
|---|---|
| lib/ | 複数スクリプトから共有されるクラス・関数（Pythonパッケージ） |
| pipelines/ | `run-*-pipeline.py` パターンのエントリポイント |
| jobs/ | ジョブファイルのCRUD + スケジューラ管理 |
| slack/ | Slack APIを直接使用するスクリプト |
| gws/ | Google Workspace APIを直接使用するスクリプト |
| data/ | CSV/JSON等のデータ加工・変換 |
| rss/ | RSSフィード取得・分割・マージ |
| ai/ | AIツール設定・ルール解決・エージェント同期 |
| setup/ | 環境構築・検証・ヘルスチェック |
| utils/ | 汎用ユーティリティ（特定ドメインに属さない） |
| tests/unit/ | 単体テスト（外部依存をモックした高速テスト） |
| tests/integration/ | 結合テスト（実際のファイルI/O・プロセス連携を含むテスト） |

## 修正対象

### ディレクトリ操作
- 10個のサブディレクトリ新規作成（lib/ 追加）
- 各スクリプトファイルの移動
- tests/ 配下の再構成（unit/, integration/）

### 新規作成ファイル

| ファイル | 内容 |
|---|---|
| `scripts/pyproject.toml` | プロジェクト設定（pytest, ruff, coverage） |
| `scripts/conftest.py` | ルートconftest（sys.path設定） |
| `scripts/Makefile` | テスト・lint実行用 |
| `scripts/lib/__init__.py` | パッケージ初期化 |
| `scripts/lib/config.py` | 設定・定数の一元管理 |
| `scripts/lib/pipeline_common.py` | パイプライン共通（リファクタリング） |
| `scripts/lib/logger.py` | ログ管理（移動） |
| `scripts/lib/version_check.py` | バージョンチェック（移動） |
| `scripts/lib/slack_client.py` | Slack操作クラス |
| `scripts/lib/gws_client.py` | GWS操作クラス |
| `scripts/lib/job_manager.py` | ジョブ管理クラス |
| `scripts/tests/conftest.py` | テスト共通fixture |
| `scripts/tests/unit/*.py` | 単体テスト群 |
| `scripts/tests/integration/*.py` | 結合テスト群 |

### パス参照の更新が必要なファイル

| 参照元 | 参照内容 |
|---|---|
| `~/Library/LaunchAgents/com.takeya.scout-daily-pipeline.plist` | `scripts/run-daily-pipeline.py` |
| `~/Library/LaunchAgents/com.takeya.scout-weekly-pipeline.plist` | `scripts/run-weekly-pipeline.py` |
| `~/Library/LaunchAgents/com.user.slack-dispatch-router.plist` | `scripts/run-slack-dispatch-router.py` |
| `~/.shared-ai/rules/filematch-dispatcher.md` | `~/scripts/resolve-shared-ai-rules.py` |
| `scripts/_pipeline_common.py` | `SCRIPTS_DIR / "notify-slack.py"` 等の相対参照 |
| `scripts/_pipeline_common.py` | `SCRIPTS_DIR / "platform-commands.sh"` |
| `scripts/_pipeline_common.py` | `SCRIPTS_DIR / "update-job.py"` |
| `scripts/_pipeline_common.py` | `SCRIPTS_DIR / "ai-cli-utils.py"` |
| `scripts/run-slack-dispatch-router.py` | `dispatch-agent-wrapper.py` 等の相対参照 |
| `scripts/run-slack-dispatch-router.py` | `SCRIPTS_DIR / f"{agent_name}.py"` による動的パイプライン参照（移動後は `pipelines/` を探索する必要あり） |
| `scripts/run-daily-pipeline.py` | `create-daily-jobs.py`, `sync-claude-agents.py` 等 |
| `scripts/run-weekly-pipeline.py` | `create-weekly-jobs.py`, `check-directory-freshness.py` 等 |
| `scripts/README.md` | 全スクリプトのパス記載 |
| `~/.shared-ai/references/agent-pipeline-run-script-guide.md` | スクリプトパス参照 |
| `~/.shared-ai/references/job-management-guide.md` | `find-job.py`, `update-job.py` パス |

### importパスの対応

`lib/` をPythonパッケージとして構成するため、用途に応じて以下の方式を使い分ける:

**方式1: conftest.py によるパス設定（テスト専用）**

ルートの `conftest.py` で `sys.path` にlib/を追加し、pytest実行時に全テストからlib配下をimport可能にする:

```python
# scripts/conftest.py（pytest実行時のみ有効）
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
```

> ⚠️ conftest.py は pytest 実行時にのみ自動読み込みされる。launchd等からの直接実行では無効。

**方式2: 各スクリプトでの明示的パス追加（エントリポイント用・必須）**

launchd や CLI から直接実行されるスクリプト（pipelines/, jobs/, slack/ 等）は、必ずこの方式を使用する:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from pipeline_common import run_pipeline, PipelineConfig
from config import ScriptsConfig
```

**方式3: 後方互換ラッパー（移行期間中）**

旧パス `scripts/_pipeline_common.py` に薄いre-exportモジュールを残し、段階的に移行:

```python
# scripts/_pipeline_common.py（後方互換ラッパー）
"""後方互換性のためのre-export。新規コードは lib.pipeline_common を直接importすること。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from pipeline_common import *  # noqa: F401, F403
```

## タスク分解

### Phase 0: テスト基盤・プロジェクト設定の構築

#### Task 0-1: pyproject.toml の作成

- **対象ファイル:** `scripts/pyproject.toml`（新規）
- **変更内容:**
  - PEP 621準拠のプロジェクトメタデータ定義
  - pytest設定（testpaths, markers, addopts）
  - coverage設定（source, omit, branch coverage有効化）
  - ruff設定（lint + format、Python 3.12ターゲット）
  - dependency-groups（PEP 735）でdev依存を管理

```toml
[project]
name = "scout-scripts"
version = "0.1.0"
requires-python = ">=3.12"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "pytest-mock>=3.14",
    "coverage[toml]>=7.6",
    "ruff>=0.11",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = ["--strict-markers", "--strict-config", "-ra"]
markers = [
    "unit: 単体テスト（外部依存なし、高速）",
    "integration: 結合テスト（ファイルI/O・プロセス連携あり）",
    "slow: 実行に時間がかかるテスト",
]

[tool.coverage.run]
source = ["lib"]
branch = true
omit = ["tests/*", "old/*"]

[tool.coverage.report]
show_missing = true
skip_empty = true
fail_under = 60

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

#### Task 0-2: conftest.py とテストヘルパーの作成

- **対象ファイル:** `scripts/conftest.py`, `scripts/tests/conftest.py`（新規）
- **変更内容:**
  - ルートconftest.py: `sys.path` にlib/を追加し、全テストからlib配下をimport可能にする
  - tests/conftest.py: 共通fixture定義（tmp_dir, mock_env, mock_slack_client等）
  - pytestマーカーの自動適用（ディレクトリベース）

#### Task 0-3: 既存テストのpytest移行

- **対象ファイル:** `scripts/tests/test-dispatch-report-path.py` → `scripts/tests/unit/test_dispatch_report_path.py`, `scripts/tests/test-rss-source-updater.py` → `scripts/tests/unit/test_rss_source_updater.py`
- **変更内容:**
  - 独自assertユーティリティ → pytest標準assert + parametrize に変換
  - テスト関数を `test_` プレフィックスの関数に分割
  - fixtureを活用した一時ファイル管理（`tmp_path`）

### Phase 1: 共通ライブラリのクラス化・モジュール化（lib/）

#### Task 1-1: lib/config.py — 設定・定数の一元管理

- **対象ファイル:** `scripts/lib/config.py`（新規）
- **変更内容:**
  - 環境変数・パス定数を `@dataclass(frozen=True)` で型安全に管理
  - `load_env()` をクラスメソッドとして整理
  - テスト時にDI（依存性注入）で差し替え可能な設計

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class ScriptsConfig:
    """スクリプト実行環境の設定。"""
    home: Path = field(default_factory=Path.home)
    scripts_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    log_base_dir: Path = field(default_factory=lambda: Path.home() / "logs" / "jobs")
    job_base_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "works" / "jobs")

    @classmethod
    def from_env(cls) -> "ScriptsConfig":
        """環境変数からオーバーライド可能な設定を生成。"""
        ...
```

#### Task 1-2: lib/slack_client.py — Slack操作のクラス化

- **対象ファイル:** `scripts/lib/slack_client.py`（新規）
- **変更内容:**
  - `_pipeline_common.py` 内のSlack関連関数（`run_slack_notify`, `run_slack_notify_async`, `_notify_slack_reply`）をクラスに集約
  - Protocol/ABCによるインターフェース定義でテスト時のモック差し替えを容易にする
  - 同期/非同期の通知メソッドを統一的なインターフェースで提供

```python
from typing import Protocol
from pathlib import Path

class SlackNotifier(Protocol):
    """Slack通知のインターフェース。"""
    def notify(self, file_path: Path, channel: str = "", thread: str = "") -> bool: ...
    def notify_async(self, file_path: Path, channel: str = "", thread: str = "") -> int: ...
    def reply(self, text: str, channel: str, thread_ts: str) -> None: ...

class SubprocessSlackNotifier:
    """notify-slack.py をsubprocessで呼び出す実装。"""
    def __init__(self, notify_script: Path, log_file: Path): ...
```

#### Task 1-3: lib/job_manager.py — ジョブ管理のクラス化

- **対象ファイル:** `scripts/lib/job_manager.py`（新規）
- **変更内容:**
  - `_pipeline_common.py` 内のジョブ関連関数（`generate_job_file`, `update_job`, `get_child_job_id`）をクラスに集約
  - ジョブのライフサイクル（生成→更新→完了/失敗）を明示的なステートマシンとして表現
  - ファイルI/Oを抽象化し、テスト時にインメモリ実装に差し替え可能にする

```python
@dataclass
class JobManager:
    """ジョブファイルのCRUD操作を管理する。"""
    job_dir: Path
    update_script: Path

    def generate(self, pipeline_name: str, base_date: str, steps: list[Step]) -> Path: ...
    def update(self, job_file: Path, job_id: str, updates: dict) -> None: ...
    def find_child_id(self, job_file: Path, job_name: str) -> str: ...
```

#### Task 1-4: lib/pipeline_common.py — 既存モジュールのリファクタリング

- **対象ファイル:** `scripts/_pipeline_common.py` → `scripts/lib/pipeline_common.py`
- **変更内容:**
  - 既存のdataclass群（Step, Executor, PipelineConfig等）はそのまま維持
  - ユーティリティ関数を適切なクラス/モジュールに分離（Slack→slack_client, Job→job_manager）
  - `ExecutionContext` に依存注入ポイントを追加（SlackNotifier, JobManager）
  - 後方互換性のため旧パスに薄いラッパー（re-export）を残す

#### Task 1-5: lib/gws_client.py — GWS操作の共通化

- **対象ファイル:** `scripts/lib/gws_client.py`（新規）
- **変更内容:**
  - GWSスクリプト群で共通するAPI認証・ファイル取得ロジックをクラスに集約
  - Google API認証フローの共通化
  - テスト用のモッククライアント提供

### Phase 2: 単体テストの作成

#### Task 2-1: test_pipeline_common.py

- **対象ファイル:** `scripts/tests/unit/test_pipeline_common.py`（新規）
- **変更内容:**
  - `Step` / `Executor` / `StepParams` のdataclass生成テスト
  - `build_agent_prompt_with_params()` のプロンプト生成ロジックテスト
  - `execute_steps()` の依存関係解決・リトライロジックテスト（subprocess をモック）
  - `now_jst()` / `generate_id()` のユーティリティテスト

#### Task 2-2: test_logger.py

- **対象ファイル:** `scripts/tests/unit/test_logger.py`（新規）
- **変更内容:**
  - `PipelineLogger` のログ出力・ローテーションテスト
  - `RotatingLineHandler` の行数制限テスト
  - `PipelineFormatter` / `JsonFormatter` のフォーマットテスト

#### Task 2-3: test_job_manager.py

- **対象ファイル:** `scripts/tests/unit/test_job_manager.py`（新規）
- **変更内容:**
  - ジョブファイル生成のJSON構造テスト
  - `_step_to_job()` の再帰変換テスト
  - `get_child_job_id()` のツリー探索テスト
  - ジョブステータス遷移テスト

#### Task 2-4: test_slack_client.py

- **対象ファイル:** `scripts/tests/unit/test_slack_client.py`（新規）
- **変更内容:**
  - `SubprocessSlackNotifier` のコマンド構築テスト（subprocess.runをモック）
  - チャンネル/スレッド引数の組み合わせテスト
  - エラーハンドリング（OSError, timeout）テスト

#### Task 2-5: test_config.py

- **対象ファイル:** `scripts/tests/unit/test_config.py`（新規）
- **変更内容:**
  - `ScriptsConfig` のデフォルト値テスト
  - 環境変数オーバーライドテスト
  - `load_env()` のlaunchd環境対応テスト（platform-commands.shをモック）

### Phase 3: 結合テストの作成

#### Task 3-1: test_pipeline_execution.py

- **対象ファイル:** `scripts/tests/integration/test_pipeline_execution.py`（新規）
- **変更内容:**
  - 最小構成のパイプライン（ScriptExecutor 1ステップ）のE2E実行テスト
  - CompositeExecutor のネスト実行テスト
  - ジョブファイル生成→更新→完了の一連フローテスト
  - タイムアウト・リトライの実動作テスト

#### Task 3-2: test_job_lifecycle.py

- **対象ファイル:** `scripts/tests/integration/test_job_lifecycle.py`（新規）
- **変更内容:**
  - `create-jobs.py` → `find-job.py` → `update-job.py` の連携テスト
  - ジョブファイルの実ファイルI/Oテスト
  - 並行アクセス時のファイルロックテスト

#### Task 3-3: test_slack_dispatch_flow.py

- **対象ファイル:** `scripts/tests/integration/test_slack_dispatch_flow.py`（新規）
- **変更内容:**
  - `run-slack-dispatch-router.py` → `dispatch-agent-wrapper.py` の連携テスト
  - レポートパス検出→Slack通知の一連フローテスト（Slack APIはモック）

### Phase 4: ディレクトリ移動・パス参照更新（既存計画の維持）

#### Task 4-1: サブディレクトリ作成とファイル移動

- **対象ファイル:** 全55スクリプト + lib/新規ファイル
- **変更内容:** 10個のサブディレクトリを作成し、各スクリプトを移動

#### Task 4-2: lib/pipeline_common.py の参照修正

- **対象ファイル:** `scripts/lib/pipeline_common.py`
- **変更内容:**
  - 分離したモジュール（slack_client, job_manager, config）へのimportに更新
  - `SCRIPTS_DIR` の定義を `Path(__file__).parent.parent`（= scripts/）に変更し、サブディレクトリ内スクリプトへのパス解決を維持
  - 各サブディレクトリ内スクリプトへの参照を新パスに更新（例: `SCRIPTS_DIR / "notify-slack.py"` → `SCRIPTS_DIR / "slack" / "notify-slack.py"`）
  - `lib/config.py` の `ScriptsConfig` にスクリプトパス解決ヘルパーを追加し、ハードコードされたパスを排除

#### Task 4-3: パイプラインスクリプトのimportパス修正

- **対象ファイル:** `scripts/pipelines/run-*.py` 全8ファイル
- **変更内容:** `from lib.pipeline_common import ...` 形式に統一

#### Task 4-4: launchd plistのパス更新

- **対象ファイル:** 3つのplistファイル
- **変更内容:** `ProgramArguments` 内のスクリプトパスを新パスに更新

#### Task 4-5: filematch-dispatcher参照パス更新

- **対象ファイル:** `~/.shared-ai/rules/filematch-dispatcher.md`
- **変更内容:** `~/scripts/resolve-shared-ai-rules.py` → `~/scripts/ai/resolve-shared-ai-rules.py`

#### Task 4-6: スクリプト間の相対参照修正

- **対象ファイル:** `run-slack-dispatch-router.py`, `run-daily-pipeline.py`, `run-weekly-pipeline.py` 等
- **変更内容:** 他スクリプトへの相対パス参照を新パスに更新

#### Task 4-7: README.md 更新

- **対象ファイル:** `scripts/README.md`
- **変更内容:** ディレクトリ構造の説明を追加、スクリプト一覧を階層別に再構成

#### Task 4-8: ドキュメント参照パス更新

- **対象ファイル:** `~/.shared-ai/references/agent-pipeline-run-script-guide.md`, `~/.shared-ai/references/job-management-guide.md`
- **変更内容:** スクリプトパスの参照を新パスに更新

### Phase 5: 自動テスト機構の構築

#### Task 5-1: git pre-commit hookへのテスト組み込み

- **対象ファイル:** `scripts/git-hooks/pre-commit`
- **変更内容:**
  - コミット前に `python3.12 -m pytest tests/unit/ -x -q` を実行
  - 単体テストが失敗した場合はコミットをブロック

#### Task 5-2: テスト実行用Makefileの作成

- **対象ファイル:** `scripts/Makefile`（新規）
- **変更内容:**
  - `make test`: 全テスト実行
  - `make test-unit`: 単体テストのみ（高速、CI向け）
  - `make test-integration`: 結合テストのみ
  - `make coverage`: カバレッジレポート生成
  - `make lint`: ruffによるlint + format check
  - `make fmt`: ruffによる自動フォーマット

```makefile
.PHONY: test test-unit test-integration coverage lint fmt

PYTHON := python3.12

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit/ -m unit

test-integration:
	$(PYTHON) -m pytest tests/integration/ -m integration

coverage:
	$(PYTHON) -m coverage run -m pytest
	$(PYTHON) -m coverage report
	$(PYTHON) -m coverage html

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

fmt:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .
```

#### Task 5-3: Kiro Agent Hookによる自動テスト実行

- **対象ファイル:** `.kiro/hooks/run-tests-on-edit.json`（新規）
- **変更内容:**
  - `scripts/lib/` 配下のファイル編集時に自動で単体テストを実行するhookを作成
  - テスト失敗時にエージェントに通知し、修正を促す

```json
{
  "name": "Run Unit Tests on Lib Edit",
  "version": "1.0.0",
  "when": {
    "type": "fileEdited",
    "patterns": ["scripts/lib/*.py"]
  },
  "then": {
    "type": "runCommand",
    "command": "cd ~/scripts && python3.12 -m pytest tests/unit/ -x -q --tb=short"
  }
}
```

## 影響範囲

- launchd定期実行（daily/weekly/slack-dispatch）のパス
- `_pipeline_common.py` 内の全スクリプト参照
- filematch-dispatcherのスクリプトパス
- 各パイプラインスクリプトのimportパス
- ドキュメント内のパス記載
- 既存テスト2ファイルのpytest移行
- git pre-commit hookの更新

## 移行戦略

段階的に移行する（テスト基盤を先に構築し、安全に移行する）:

1. **Phase 0**: テスト基盤構築（pyproject.toml, conftest.py, 既存テスト移行）
   - 移行前の動作を保証するテストを先に整備する
2. **Phase 1**: lib/ パッケージ作成（クラス化・モジュール分離）
   - 既存コードからロジックを抽出し、テストを書きながらクラス化
   - 後方互換ラッパーにより既存スクリプトは変更なしで動作継続
3. **Phase 2**: 単体テスト作成
   - lib/ の各モジュールに対する単体テストを網羅的に作成
   - カバレッジ60%以上を目標
4. **Phase 3**: 結合テスト作成
   - パイプライン実行フロー、ジョブライフサイクル等のE2Eテスト
5. **Phase 4**: ディレクトリ移動・パス参照更新
   - 影響範囲が小さいディレクトリから開始（`utils/`, `data/`, `rss/`）
   - 次に `gws/`, `slack/`, `ai/`, `setup/` を移動
   - 最後に `pipelines/`, `jobs/` を移動（launchd plist更新を伴う）
   - **各移動後**: `make test` で全テストがパスすることを確認
6. **Phase 5**: 自動テスト機構の構築
   - pre-commit hook, Makefile, Kiro Agent Hook の設定
   - **各Phase後**: launchd再読み込み + パイプライン動作確認

## 代替案の検討

### ディレクトリ構造

| 方式 | メリット | デメリット |
|---|---|---|
| **サブディレクトリ分割 + lib/パッケージ（本案）** | 見通し良好、テスタビリティ高、関連ファイルが近接 | importパス・参照パスの大量更新が必要 |
| **ファイル名プレフィックス方式** | パス変更不要、即座に適用可能 | ファイル名が長くなる、ソート順が変わる、テスタビリティ改善なし |
| **完全Pythonパッケージ化（src layout）** | import管理が正式、pip install -e 可能 | 大規模な構造変更、既存の実行方法（`python3.12 scripts/xxx.py`）が使えなくなる |
| **uv init --package** | モダンなパッケージ管理、lockfile対応 | スクリプト集としてはオーバーエンジニアリング、launchd連携が複雑化 |

### テストフレームワーク

| 方式 | メリット | デメリット |
|---|---|---|
| **pytest（本案）** | デファクトスタンダード、豊富なプラグイン、parametrize/fixture | 追加依存 |
| **unittest（標準ライブラリ）** | 追加依存なし | 冗長なboilerplate、fixtureが貧弱 |
| **独自テストフレームワーク（現状）** | 依存なし、シンプル | エコシステムの恩恵なし、CI連携困難、カバレッジ計測不可 |

### クラス化の粒度

| 方式 | メリット | デメリット |
|---|---|---|
| **Protocol + dataclass（本案）** | 型安全、DI容易、テスタビリティ高 | 学習コスト、既存コードとの乖離 |
| **関数ベース維持 + モジュール分割のみ** | 変更量最小、既存パターン維持 | テスト時のモック困難、依存関係が暗黙的 |
| **ABC（抽象基底クラス）** | 強制力が高い | Pythonでは過剰、Protocolで十分 |

## リスク・注意点

- `_pipeline_common.py` が `SCRIPTS_DIR / "notify-slack.py"` のように相対パスでスクリプトを参照しているため、移動後にパス解決が壊れる可能性が高い。`SCRIPTS_DIR` の定義を `lib/` ではなく `scripts/`（親ディレクトリ）を指すように変更し、参照パスにサブディレクトリを含める必要がある
- `run-slack-dispatch-router.py` が `SCRIPTS_DIR / f"{agent_name}.py"` で動的にパイプラインスクリプトを参照している。`slack/` に移動後は `SCRIPTS_DIR` が `slack/` を指すため、パイプラインスクリプトの探索ロジックを `scripts/pipelines/` を明示的に参照するよう変更する必要がある
- `run-weekly-pipeline.py` が `SCRIPTS_DIR / "run-poc-planner-pipeline.py"` 等で同階層のパイプラインスクリプトを参照している。移動後は同じ `pipelines/` 内なので `Path(__file__).parent / "run-poc-planner-pipeline.py"` に変更するか、`SCRIPTS_DIR` 経由で `pipelines/` を明示する
- launchd plist更新後は `launchctl unload` → `launchctl load` が必要
- 移行中にパイプラインが実行されると中途半端な状態になるため、launchdを一時停止してから作業する
- lib/ パッケージ化により `sys.path` 操作が増えるが、conftest.py（テスト用）と各エントリポイントの冒頭（本番用）で管理する
- 後方互換ラッパーは移行完了後に削除する（デッドコード化を防ぐ）
- pytest導入により `pytest`, `pytest-cov`, `pytest-mock` の追加インストールが必要（`pip install` で対応）
- クラス化は段階的に行い、一度に全スクリプトを書き換えない（動作するコードを壊さない）

## テスト計画

### 自動テスト（pytest）

- [ ] `python3.12 -m pytest tests/unit/ -v` で全単体テストがパスすること
- [ ] `python3.12 -m pytest tests/integration/ -v` で全結合テストがパスすること
- [ ] `python3.12 -m coverage run -m pytest && python3.12 -m coverage report` でカバレッジ60%以上
- [ ] `python3.12 -m ruff check .` でlintエラーなし

### 手動テスト（移行後の動作確認）

- [ ] 全スクリプトが新パスで `python3.12 scripts/{subdir}/{script}.py --help` 等で起動できること
- [ ] `from lib.pipeline_common import run_pipeline, PipelineConfig` が成功すること
- [ ] launchd経由でdaily/weeklyパイプラインが正常に実行されること
- [ ] `resolve-shared-ai-rules.py` が新パスで正常動作すること
- [ ] `run-slack-dispatch-router.py` が新パスで正常動作すること
- [ ] `scripts/README.md` の記載が新構造と一致すること
- [ ] 後方互換ラッパー経由での既存import（`from _pipeline_common import ...`）が動作すること

### テスト分類とマーカー

| マーカー | 実行タイミング | 対象 |
|---|---|---|
| `@pytest.mark.unit` | 毎コミット（pre-commit hook） | lib/ の純粋ロジック |
| `@pytest.mark.integration` | PR作成時・手動実行 | ファイルI/O・プロセス連携 |
| `@pytest.mark.slow` | 日次実行 | タイムアウト・リトライの実動作 |

## 技術選定の根拠

### pytest を選択した理由

- Pythonテストのデファクトスタンダード（[pytest公式ドキュメント](https://docs.pytest.org/en/stable/explanation/goodpractices.html)）
- `assert` 文のみでテストが書ける（unittest.TestCase不要）
- `@pytest.mark.parametrize` による効率的なテストケース記述
- `tmp_path` fixture による一時ファイル管理
- `pytest-mock` によるモック/パッチの簡潔な記述
- `pytest-cov` によるカバレッジ計測の統合

### dataclass + Protocol を選択した理由

- Python 3.12標準ライブラリのみで型安全な設計が可能（外部依存なし）
- `@dataclass(frozen=True)` でイミュータブルな設定オブジェクトを表現
- `Protocol` で構造的部分型（structural subtyping）を実現し、テスト時のモック差し替えが容易
- Pydanticは外部依存であり、バリデーション要件がないスクリプト集には過剰

### pyproject.toml 一元管理を選択した理由

- PEP 621/735準拠のモダンなプロジェクト設定（[pydevtools.com](https://pydevtools.com/handbook/explanation/modern-python-project-setup-guide-for-ai-assistants/)）
- pytest, coverage, ruff の設定を1ファイルに集約
- setup.cfg, setup.py, tox.ini 等の分散した設定ファイルを排除
- uv対応（将来的にuv syncでの依存管理に移行可能）
