# pipeline-redesign: パイプラインスクリプトの統一ステップモデル再設計

## 変更種別

refactor

## 概要

- `_pipeline_common.py` を統一的な「ステップ」概念に再設計する
- `Step` / `Executor` / `StepParams` dataclass による宣言的パイプライン定義に移行する
- 各パイプラインスクリプトを `build_steps()` 方式に統合する
- `invoke-agent.py`（手動実行用CLIラッパー）を新規作成する
- `dispatch-agent-wrapper.py` を新パラメータ方式に移行する

## 問題・背景

- 現状の `_pipeline_common.py` は `NOTIFY_FILE_MAP` / `build_prompt()` / `resolve_notify_path` 等で通知・出力を制御しているが、一貫性がない
- ジョブ定義（`create-daily-jobs.py`）とパイプライン定義（`run-daily-pipeline.py`）が二重管理されている
- hookコールバック（`pre_pipeline_hook`, `rss_fetch_hook`, `post_agents_hook` 等）が散在し、実行フローが追いにくい
- サブパイプライン（`run-gws-trend-scout-pipeline.py` 等）が独立スクリプトとして存在し、親パイプラインとの関係が暗黙的

## 修正対象

### 新規作成
- `~/scripts/invoke-agent.py`

### 大幅改修
- `~/scripts/_pipeline_common.py`
- `~/scripts/ai-cli-utils.py`
- `~/scripts/run-daily-pipeline.py`
- `~/scripts/run-weekly-pipeline.py`
- `~/scripts/run-github-org-trend-scout-pipeline.py`
- `~/scripts/run-github-repo-analysis-pipeline.py`
- `~/scripts/dispatch-agent-wrapper.py`

### 廃止
- `~/scripts/run-gws-trend-scout-pipeline.py`（親パイプラインにインライン化）
- `~/scripts/run-academic-trend-scout-pipeline.py`（親パイプラインにインライン化）
- `~/scripts/create-daily-jobs.py`（`generate_job_file` で自動生成）
- `~/scripts/create-weekly-jobs.py`（`generate_job_file` で自動生成）

### エージェントプロンプト
- `~/.shared-ai/prompts/web-searcher.md`（dispatch-wrapper判定セクション削除）

## タスク分解

### Task 1: _pipeline_common.py の再設計

- **対象ファイル:** `~/scripts/_pipeline_common.py`, `~/scripts/ai-cli-utils.py`
- **変更内容:**
  - `Step` / `Executor`（AgentExecutor, ScriptExecutor, CompositeExecutor）/ `StepParams` / `RetryPolicy` dataclass を追加
  - `PipelineConfig` を新設計に変更（`name` + `build_steps` + `default_base_date` の3フィールド）
  - `PipelineContext` dataclass を追加（`base_date`, `log_dir`, `use_job_file`, `slack_channel`, `slack_thread_ts`）
  - `run_pipeline()` を再帰的ステップ実行に変更（`execute_steps()` の再帰呼び出し）
  - `generate_job_file(steps)` を実装（Step ツリー → ジョブファイル自動生成）
  - `NOTIFY_FILE_MAP` / `resolve_notify_path` / `WEEKLY_PIPELINE_MODE_AGENTS` / 全hookコールバック / `build_prompt` を廃止
  - 同期/非同期実行、タイムアウト、リトライの共通ロジックを実装
  - `ai-cli-utils.py` の `build_ai_command()` を拡張: `StepParams` からYAMLブロックを生成しプロンプト冒頭に埋め込む機能を追加

### Task 2: 各パイプラインスクリプトの移行

- **対象ファイル:** `run-daily-pipeline.py`, `run-weekly-pipeline.py`, `run-github-org-trend-scout-pipeline.py`, `run-github-repo-analysis-pipeline.py`
- **変更内容:**
  - `AGENTS` + `NOTIFY_FILE_MAP` + `build_prompt()` + hook関数群を `build_steps()` に統合
  - RSS取得・鮮度チェック等の既存hookは `ScriptExecutor` ステップとして定義
  - 各エージェントは `AgentExecutor` ステップとして定義（全パラメータ明示）
  - daily/weeklyの旧サブパイプラインの内容を `CompositeExecutor` + `Step.steps` として親パイプラインにインライン化
  - `create-daily-jobs.py`, `create-weekly-jobs.py` は廃止（`generate_job_file` で自動生成）

### Task 3: invoke-agent.py の新規作成

- **対象ファイル:** `~/scripts/invoke-agent.py`（新規）
- **変更内容:** 手動実行用のCLIラッパー。コマンドライン引数から `Step` を1つ構築し、`run_pipeline()` と同じ実行ロジックで処理する。パイプラインと手動実行で実行パスが統一される

### Task 4: dispatch-agent-wrapper.py の移行

- **対象ファイル:** `~/scripts/dispatch-agent-wrapper.py`
- **変更内容:** エージェント呼び出し時に `Step` + `StepParams` を構築する方式に移行。プロンプト内の `[引き継ぎ事項:` 文言埋め込みを廃止し、`StepParams.slack.enabled: false` で通知スキップを制御

### Task 5: 全エージェントプロンプトから文言解析ロジックを削除

- **対象ファイル:** `~/.shared-ai/prompts/web-searcher.md`
- **変更内容:** `dispatch-agent-wrapper` 判定セクション（Phase 4のスキップ条件）を削除。`agent_params` の解析手順（agent-common.md 参照）に置き換え

### Task 6: 動作確認

- **変更内容:**
  - `run-daily-pipeline.py` が新しい `build_steps()` 方式で全ステップを正常実行できること
  - `invoke-agent.py` で手動実行時に正しいYAMLブロックが生成されること
  - dispatch-agent-wrapper 経由で web-searcher を呼び出し、Slack通知がスキップされること
  - launchd経由の自動実行（daily/weekly）が新設計で正常動作すること

## 設計方針

### 統一ステップモデル

パイプラインは**ステップのツリー**として定義する。各ステップは「何を実行するか」の種別に関わらず、同じインターフェースで定義・実行される。

```
Pipeline (= root Step)
├── Step (= child job)
├── Step (= child job, with nested steps)
│   ├── Step (= grandchild job)
│   └── Step (= grandchild job)
└── Step (= child job)
```

### PipelineConfig（最小化）

```python
@dataclass
class PipelineConfig:
    name: str
    build_steps: Callable[[str, PipelineContext], list[Step]]
    default_base_date: Callable[[], str]
```

### 実行フロー

1. オプション解析 → PipelineContext 構築
2. `steps = config.build_steps(base_date, context)` でステップツリー生成
3. `job_file = generate_job_file(config.name, base_date, steps)` でジョブファイル自動生成
4. `execute_steps(steps, ExecutionContext(...))` でステップツリーを再帰的に実行
5. 親ジョブ完了処理

### 廃止対象

| 廃止 | 理由 |
|------|------|
| `NOTIFY_FILE_MAP` | `step.params.slack` に統合 |
| `resolve_notify_path` | `step.params.output.path` に統合 |
| `WEEKLY_PIPELINE_MODE_AGENTS` | `build_steps` 内でプロンプト構築時に判定 |
| `AGENTS` リスト | `build_steps` が `Step` ツリーを返す |
| 全hookコールバック | `ScriptExecutor` ステップとして定義 |
| `build_prompt` | `AgentExecutor.prompt_text` に統合 |
| `create-daily-jobs.py` / `create-weekly-jobs.py` | `generate_job_file(steps)` で自動生成 |
| サブパイプラインスクリプト | `CompositeExecutor` + `Step.steps` で表現 |
| dispatch-agent-wrapper の文言解析 | `StepParams.slack.enabled: false` で制御 |

## 影響範囲

- 全パイプラインスクリプト（daily, weekly, github-org, github-repo-analysis）
- launchd plist（引数変更がなければ影響なし）
- dispatch-agent-wrapper 経由の全エージェント呼び出し
- web-searcher.md（dispatch-wrapper判定セクション削除）

## リスク・注意点

- **移行中のlaunchd停止**: 実施中は `manage-scheduler.py unload` で自動実行を停止し、移行完了後に `manage-scheduler.py load` で再開すること
- **一括移行が必要**: 段階的移行は中途半端な状態を生む。全パイプラインを一度に移行する
- **launchd plist**: パイプラインスクリプトのインターフェース変更がlaunchd経由の自動実行に影響しないことを確認する

## テスト計画

- [ ] `run-daily-pipeline.py` が新しい `build_steps()` 方式で全ステップを正常実行できること
- [ ] `invoke-agent.py` で手動実行時に正しいYAMLブロックが生成されること
- [ ] tech-trend-scout を新パラメータ方式で実行し、output/log/slack が正しく動作すること
- [ ] web-searcher を `slack.enabled: false` で実行し、Slack通知がスキップされること
- [ ] dispatch-agent-wrapper 経由で web-searcher を呼び出し、`slack.enabled: false` が正しく伝播すること
- [ ] launchd経由の自動実行（daily/weekly）が新設計で正常動作すること
- [ ] `generate_job_file` が Step ツリーから正しいジョブファイルを生成すること
- [ ] CompositeExecutor のネストされたステップが正しく再帰実行されること

## 前提・依存

- `extract-agent-common-module` issue の Task 1〜6 が完了していること（完了済み）
- `agent-params-schema` issue が完了していること（agent_params YAMLブロックの仕様が確定している必要あり）
