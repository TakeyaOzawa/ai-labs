# remove-pipeline-common-wrapper: 後方互換ラッパー `_pipeline_common.py` の削除

## 変更種別

refactor

## 概要

- `scripts/_pipeline_common.py`（後方互換re-exportラッパー）を削除する
- 全エントリポイントのimport文を `lib/` 直接import形式に統一する
- 同時に不要になったルート直下の旧ファイル（`logger.py`, `_pipeline_common_backup.py`）を削除する
- 旧テストファイル（`tests/test-dispatch-report-path.py`, `tests/test-rss-source-updater.py`）を削除する

## 問題・背景

- `scripts-directory-restructure` issue（Phase 0〜5）完了により、全スクリプトが新ディレクトリ構造で動作している
- `_pipeline_common.py` は移行期間中の後方互換ラッパーとして残されたが、全スクリプトが既に `sys.path.insert(0, parent.parent)` で `scripts/` をパスに含めているため、直接importに切り替え可能
- ラッパーが残っていると「どちらからimportすべきか」の混乱を招き、デッドコード化のリスクがある

## 実施条件（全て満たされた時点で着手可能）

| # | 条件 | 確認方法 | 状態 |
|---|---|---|---|
| 1 | 全パイプラインが新パスで正常起動確認済み | `verify-scripts.py` 全パス | ✅ 2026-05-19確認 |
| 2 | launchd経由のdaily pipeline定期実行が1回以上成功 | `~/logs/jobs/scout_daily/pipeline.log` の最新実行結果 | ⬜ 翌朝2:00 JST |
| 3 | launchd経由のweekly pipeline定期実行が1回以上成功 | `~/logs/jobs/scout_weekly/pipeline.log` の最新実行結果 | ⬜ 次の土曜3:30 JST |
| 4 | slack-dispatch-router が新パスで正常動作 | `launchctl list` で `last_exit_code: 0` | ✅ 2026-05-19確認 |

> **判断**: 条件2が満たされた時点で着手可能（条件3は週次のため待たなくてよい。daily成功で十分な信頼性）。

## 修正対象

### 削除ファイル

| ファイル | 理由 |
|---|---|
| `scripts/_pipeline_common.py` | 後方互換ラッパー本体 |
| `scripts/_pipeline_common_backup.py` | 移行前のバックアップ |
| `scripts/_version_check.py` | ✅ 削除済み（2026-05-19） |
| `scripts/logger.py`（ルート） | `lib/logger.py` に移行済み |
| `scripts/tests/test-dispatch-report-path.py` | `tests/unit/test_dispatch_report_path.py` に移行済み |
| `scripts/tests/test-rss-source-updater.py` | `tests/unit/test_rss_source_updater.py` に移行済み |

### import書き換え対象（10ファイル）

| ファイル | 現在のimport | 変更後 |
|---|---|---|
| `pipelines/run-daily-pipeline.py` | `from _pipeline_common import ...` | `from models import ...; from pipeline_engine import ...` |
| `pipelines/run-weekly-pipeline.py` | 同上 | 同上 + `from pipeline_engine import _notify_slack_reply` |
| `pipelines/run-freshness-pipeline.py` | 同上 | 同上 |
| `pipelines/run-poc-planner-pipeline.py` | 同上 | 同上 |
| `pipelines/run-github-org-trend-scout-pipeline.py` | 同上 | 同上 |
| `pipelines/run-github-repo-analysis-pipeline.py` | `from _pipeline_common import run_ai_command, run_slack_notify, load_env` | `from pipeline_engine import run_ai_command, run_slack_notify; from config import load_env` |
| `pipelines/run-academic-trend-scout-pipeline.py` | 同上 | 同上 + `from pipeline_engine import _notify_slack_reply` |
| `pipelines/run-gws-trend-scout-pipeline.py` | 同上 | 同上 |
| `slack/dispatch-agent-wrapper.py` | `from _pipeline_common import ...` | `from models import ...; from pipeline_engine import ...; from config import load_env; from logger import PipelineLogger` |
| `ai/invoke-agent.py` | `from _pipeline_common import InputParams` | `from models import InputParams` |

### 追加修正（文字列参照）

| ファイル | 修正内容 |
|---|---|
| `slack/run-slack-dispatch-router.py` | `_pipeline_uses_run_pipeline()` 内の `"_pipeline_common" in content` → `"from pipeline_engine" in content` or `"from models" in content` に変更 |
| `setup/check-env.py` | `used_by` 文字列リテラル内の `_pipeline_common.py` → `lib/pipeline_engine.py` に更新 |

### 追加修正（SCRIPTS_DIR パス不整合 — 既存バグ）

以下のファイルは `SCRIPTS_DIR = Path(__file__).parent`（= 自ディレクトリ）を定義しているが、他サブディレクトリのスクリプトを参照しており、パスが壊れている。本issue実施時に合わせて修正する:

| ファイル | 壊れている参照 | 正しいパス |
|---|---|---|
| `pipelines/run-academic-trend-scout-pipeline.py` | `SCRIPTS_DIR / "update-job.py"` | `SCRIPTS_DIR / "jobs" / "update-job.py"` |
| `pipelines/run-academic-trend-scout-pipeline.py` | `SCRIPTS_DIR / "split-academic-feeds.py"` | `SCRIPTS_DIR / "rss" / "split-academic-feeds.py"` |
| `pipelines/run-academic-trend-scout-pipeline.py` | `SCRIPTS_DIR / "merge-academic-intermediate-files.py"` | `SCRIPTS_DIR / "rss" / "merge-academic-intermediate-files.py"` |
| `pipelines/run-gws-trend-scout-pipeline.py` | `SCRIPTS_DIR / "filter-gws-drive-metadata.py"` | `SCRIPTS_DIR / "gws" / "filter-gws-drive-metadata.py"` |
| `pipelines/run-gws-trend-scout-pipeline.py` | `SCRIPTS_DIR / "summarize-filtered-metadata.py"` | `SCRIPTS_DIR / "gws" / "summarize-filtered-metadata.py"` |
| `pipelines/run-gws-trend-scout-pipeline.py` | `SCRIPTS_DIR / "find-job.py"` | `SCRIPTS_DIR / "jobs" / "find-job.py"` |
| `pipelines/run-gws-trend-scout-pipeline.py` | `SCRIPTS_DIR / "update-job.py"` | `SCRIPTS_DIR / "jobs" / "update-job.py"` |
| `pipelines/run-gws-trend-scout-pipeline.py` | `SCRIPTS_DIR / "merge-gws-intermediate-files.py"` | `SCRIPTS_DIR / "gws" / "merge-gws-intermediate-files.py"` |

修正方針: `SCRIPTS_DIR = Path(__file__).parent` → `SCRIPTS_DIR = Path(__file__).parent.parent` に変更し、`scripts/` を指すように統一する。

> ⚠️ 上記2ファイルは `# DEPRECATED: run-daily-pipeline.py にインライン化済み` とマークされている。パス修正ではなく削除を検討すべき。

## 推奨追加事項（一緒にやっておくべきこと）

### 1. DEPRECATEDスクリプトの削除

以下のスクリプトは `run-daily-pipeline.py` にインライン化済みで、単独実行はパス不整合で壊れている。本issue実施時に削除する:

- `pipelines/run-academic-trend-scout-pipeline.py`
- `pipelines/run-gws-trend-scout-pipeline.py`

削除後、`ai-cli-utils.py` の `scan_agents()` が `pipelines/` をglobしているため、これらが消えても問題ないことを確認する（パイプライン一覧から除外されるだけ）。

### 2. `__pycache__` の一括削除

ディレクトリ移動前の古い `.pyc` ファイルが `scripts/__pycache__/` に残っている。削除する:

```bash
rm -rf ~/scripts/__pycache__
find ~/scripts -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### 3. `.shared-ai/references/agent-pipeline-run-script-guide.md` の更新

`_pipeline_common.py` 削除後、ガイド内の「`_pipeline_common.py` — 共通ユーティリティ + PipelineConfig + run_pipeline()」の記述を `lib/models.py` + `lib/pipeline_engine.py` に更新する。

### 4. `scripts/README.md` の後方互換ラッパー記載削除

README内に `_pipeline_common.py` への言及があれば削除する。

## タスク分解

### Task 1: import文の一括書き換え

- **対象ファイル:** 上記10ファイル
- **変更内容:**
  - `from _pipeline_common import ...` を `from models import ...; from pipeline_engine import ...` 等に分割
  - 各ファイルの冒頭には既に `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` があるため、`scripts/` がパスに含まれている
  - `lib/` もパスに追加する（`sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))`）

### Task 2: 文字列参照の修正

- **対象ファイル:** `slack/run-slack-dispatch-router.py`, `setup/check-env.py`
- **変更内容:** `_pipeline_common` への文字列参照を新モジュール名に更新

### Task 3: 不要ファイルの削除

- **対象ファイル:** 上記6ファイル
- **変更内容:** `rm` で削除

### Task 4: 動作検証

- **変更内容:**
  - `python3.12 -m pytest tests/ -q` で全テストパス
  - `python3.12 scripts/setup/verify-scripts.py` で全ファイルOK
  - `python3.12 scripts/pipelines/run-daily-pipeline.py --no-job-file $(date -v-1d +%Y-%m-%d)` で手動実行確認

## 影響範囲

- パイプラインスクリプト 8ファイルのimport文
- slackスクリプト 1ファイルのimport文 + パイプライン判定ロジック
- aiスクリプト 1ファイルのimport文
- setupスクリプト 1ファイルの文字列リテラル
- テスト: 影響なし（テストはlib/を直接importしている）
- launchd実行: 影響なし（sys.pathは各スクリプト冒頭で設定済み）

## テスト計画

- [ ] `python3.12 -m pytest tests/ -q` で116テスト全パス
- [ ] `python3.12 scripts/setup/verify-scripts.py` で全ファイルOK
- [ ] `python3.12 scripts/pipelines/run-daily-pipeline.py --no-job-file` で手動実行成功
- [ ] `grep -rl "_pipeline_common" ~/scripts/ | grep -v __pycache__` で参照残存なし
- [ ] `manage-scheduler.py reload` 後に `list` で全ジョブ `last_exit_code: 0`
- [ ] `find ~/scripts -type d -name __pycache__` で古いキャッシュが残っていないこと
- [ ] DEPRECATEDスクリプト削除後に `ai-cli-utils.py` の `scan_agents()` が正常動作すること
