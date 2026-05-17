# scripts-directory-restructure: scriptsディレクトリの階層構造整理

## 変更種別

refactor

## 概要

- `~/scripts/` 配下の50+スクリプトをドメイン別サブディレクトリに整理する
- フラット構造から階層構造に移行し、見通しと保守性を改善する

## 問題・背景

- 現在52ファイルがフラットに配置されており、目的のスクリプトを見つけにくい
- 機能的に関連するスクリプト群（Slack連携、GWS連携、パイプライン等）が混在している
- スクリプト追加のたびに一覧が肥大化し、READMEの主要スクリプト表も長大になっている

## 新しいディレクトリ構造

```
scripts/
├── README.md
├── platform-commands.sh          # シェルユーティリティ（パス参照が広範なためルートに残す）
├── _pipeline_common.py           # 共通モジュール（importパス維持のためルートに残す）
├── _version_check.py
├── logger.py
│
├── pipelines/                    # パイプライン実行エントリポイント
│   ├── run-daily-pipeline.py
│   ├── run-weekly-pipeline.py
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
│   └── update-slack-user-directory.py
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
│   ├── resolve-shared-ai-rules.py
│   └── sync-claude-agents.py
│
├── setup/                        # セットアップ・検証
│   ├── setup-shared-ai.py
│   ├── setup-symlinks.py
│   ├── verify-shared-ai-structure.py
│   ├── check-env.py
│   └── check-directory-freshness.py
│
├── utils/                        # 汎用ユーティリティ
│   ├── decode-b64-write.py
│   ├── encode-to-b64.py
│   ├── epoch-to-jst.py
│   ├── get-jst-date.py
│   └── free-notion-mcp-port.py
│
├── git-hooks/                    # 既存のまま
│   └── pre-commit
│
└── old/                          # 既存のまま
```

## 分類基準

| ディレクトリ | 分類基準 |
|---|---|
| pipelines/ | `run-*-pipeline.py` パターンのエントリポイント |
| jobs/ | ジョブファイルのCRUD + スケジューラ管理 |
| slack/ | Slack APIを直接使用するスクリプト |
| gws/ | Google Workspace APIを直接使用するスクリプト |
| data/ | CSV/JSON等のデータ加工・変換 |
| rss/ | RSSフィード取得・分割・マージ |
| ai/ | AIツール設定・ルール解決・エージェント同期 |
| setup/ | 環境構築・検証・ヘルスチェック |
| utils/ | 汎用ユーティリティ（特定ドメインに属さない） |

## 修正対象

### ディレクトリ操作
- 9つのサブディレクトリ新規作成
- 各スクリプトファイルの移動

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
| `scripts/run-daily-pipeline.py` | `create-daily-jobs.py`, `sync-claude-agents.py` 等 |
| `scripts/run-weekly-pipeline.py` | `create-weekly-jobs.py`, `check-directory-freshness.py` 等 |
| `scripts/README.md` | 全スクリプトのパス記載 |
| `~/.shared-ai/references/agent-pipeline-run-script-guide.md` | スクリプトパス参照 |
| `~/.shared-ai/references/job-management-guide.md` | `find-job.py`, `update-job.py` パス |

### importパスの対応

`_pipeline_common.py` をルートに残すため、サブディレクトリ内のスクリプトからimportする場合は `sys.path` の追加が必要:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _pipeline_common import run_pipeline, PipelineConfig
```

## タスク分解

### Task 1: サブディレクトリ作成とファイル移動

- **対象ファイル:** 全52スクリプト
- **変更内容:** 9つのサブディレクトリを作成し、各スクリプトを移動

### Task 2: _pipeline_common.py の相対参照修正

- **対象ファイル:** `scripts/_pipeline_common.py`
- **変更内容:** `SCRIPTS_DIR / "notify-slack.py"` 等の参照を新パスに更新。または `SCRIPTS_DIR` の定義を維持しつつサブディレクトリを探索するヘルパーを追加

### Task 3: パイプラインスクリプトのimportパス修正

- **対象ファイル:** `scripts/pipelines/run-*.py` 全6ファイル
- **変更内容:** `sys.path` にルートを追加して `_pipeline_common` のimportを維持

### Task 4: launchd plistのパス更新

- **対象ファイル:** 3つのplistファイル
- **変更内容:** `ProgramArguments` 内のスクリプトパスを新パスに更新

### Task 5: filematch-dispatcher参照パス更新

- **対象ファイル:** `~/.shared-ai/rules/filematch-dispatcher.md`
- **変更内容:** `~/scripts/resolve-shared-ai-rules.py` → `~/scripts/ai/resolve-shared-ai-rules.py`

### Task 6: スクリプト間の相対参照修正

- **対象ファイル:** `run-slack-dispatch-router.py`, `run-daily-pipeline.py`, `run-weekly-pipeline.py` 等
- **変更内容:** 他スクリプトへの相対パス参照を新パスに更新

### Task 7: README.md 更新

- **対象ファイル:** `scripts/README.md`
- **変更内容:** ディレクトリ構造の説明を追加、スクリプト一覧を階層別に再構成

### Task 8: ドキュメント参照パス更新

- **対象ファイル:** `~/.shared-ai/references/agent-pipeline-run-script-guide.md`, `~/.shared-ai/references/job-management-guide.md`
- **変更内容:** スクリプトパスの参照を新パスに更新

## 影響範囲

- launchd定期実行（daily/weekly/slack-dispatch）のパス
- `_pipeline_common.py` 内の全スクリプト参照
- filematch-dispatcherのスクリプトパス
- 各パイプラインスクリプトのimportパス
- ドキュメント内のパス記載

## 移行戦略

段階的に移行する:

1. **Phase 1**: 影響範囲が小さいディレクトリから開始（`utils/`, `data/`, `rss/`）
2. **Phase 2**: `gws/`, `slack/`, `ai/`, `setup/` を移動
3. **Phase 3**: `pipelines/`, `jobs/` を移動（launchd plist更新を伴う）
4. **各Phase後**: launchd再読み込み + パイプライン動作確認

## 代替案の検討

| 方式 | メリット | デメリット |
|---|---|---|
| **サブディレクトリ分割（本案）** | 見通し良好、関連ファイルが近接 | importパス・参照パスの大量更新が必要 |
| **ファイル名プレフィックス方式** | パス変更不要、即座に適用可能 | ファイル名が長くなる、ソート順が変わる |
| **Pythonパッケージ化** | import管理が正式、テスト容易 | `__init__.py` 追加、既存の実行方法変更 |

## リスク・注意点

- `_pipeline_common.py` が `SCRIPTS_DIR / "notify-slack.py"` のように相対パスでスクリプトを参照しているため、移動後にパス解決が壊れる可能性が高い
- launchd plist更新後は `launchctl unload` → `launchctl load` が必要
- 移行中にパイプラインが実行されると中途半端な状態になるため、launchdを一時停止してから作業する

## テスト計画

- [ ] 全スクリプトが新パスで `python3.12 scripts/{subdir}/{script}.py --help` 等で起動できること
- [ ] `python3.12 -c "import sys; sys.path.insert(0, 'scripts'); from _pipeline_common import run_pipeline"` が成功すること
- [ ] launchd経由でdaily/weeklyパイプラインが正常に実行されること
- [ ] `resolve-shared-ai-rules.py` が新パスで正常動作すること
- [ ] `run-slack-dispatch-router.py` が新パスで正常動作すること
- [ ] `scripts/README.md` の記載が新構造と一致すること
