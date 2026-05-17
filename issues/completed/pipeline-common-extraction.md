# pipeline-common-extraction: パイプラインスクリプト共通化

## 変更種別

refactor

## 概要

- `scripts/run-daily-pipeline.py` と `scripts/run-weekly-pipeline.py` で重複している共通ロジック（70-80%）を `scripts/_pipeline_common.py` に抽出し、各パイプラインファイルは固有の設定と差分ロジックのみを保持する構成にリファクタリングする
- 今後パイプラインが増える見込みがあるため、3つ目以降の追加を低コストにする

## 問題・背景

- 現在 daily / weekly の2ファイルで以下が完全にコピペ状態:
  - ユーティリティ関数群（`now_jst`, `rotate_log`, `load_env`, `run_kiro_cli`, `log_error`）
  - ヘルパー関数群（`start_caffeinate`, `stop_caffeinate`, `get_child_job_id`, `update_job`）
  - パイプライン実行の骨格（オプション解析 → 環境準備 → ジョブファイル → エージェント実行ループ → 通知 → サマリー）
- 片方にバグ修正や改善を入れた際、もう片方への反映漏れリスクがある
- 今後 monthly 等のパイプラインが追加される場合、さらにコピペが増える

## 設計方針

### アーキテクチャ: 設定dict + 共通runner関数（クラス継承は使わない）

各パイプラインファイルが「設定を定義して共通のrunner関数に渡す」フラットな構成とする。
理由: スクリプトの規模（各300行程度）に対してクラス継承は過剰。読みやすさ・デバッグしやすさを優先。

### ファイル構成

```
scripts/
├── _pipeline_common.py         # 共通ユーティリティ + パイプラインrunner（内部モジュール）
├── run-daily-pipeline.py       # daily固有の設定 + フック関数
└── run-weekly-pipeline.py      # weekly固有の設定 + フック関数
```

### _pipeline_common.py に抽出するもの

#### 1. 定数

```python
JST = timezone(timedelta(hours=9))
HOME = Path.home()
SCRIPTS_DIR = Path(__file__).parent
PLATFORM_CMD = SCRIPTS_DIR / "platform-commands.sh"
MAX_LOG_LINES = 1000
MAX_AGENT_LOG_LINES = 500
```

#### 2. ユーティリティ関数（そのまま移動）

- `now_jst()`
- `rotate_log()`
- `load_env()`
- `run_kiro_cli()`
- `log_error()`
- `start_caffeinate()` / `stop_caffeinate()`
- `get_child_job_id()`
- `update_job()`

#### 3. パイプライン設定の型定義（TypedDict or dataclass）

```python
@dataclass
class PipelineConfig:
    name: str                          # "daily" | "weekly"
    log_dir: Path                      # LOG_DIR
    agents: list[str]                  # AGENTS リスト
    notify_file_map: dict[str, str]    # NOTIFY_FILE_MAP
    create_jobs_script: str            # "create-daily-jobs.py" | "create-weekly-jobs.py"
    default_base_date: Callable[[], str]  # 基準日デフォルト計算
    # RSS取得: 案A（下記）か案B（rss_fetch_hook）か未確定。末尾「設計上の判断メモ」参照
    rss_categories: list[str]          # RSSフィード取得カテゴリ（案A用）
    rss_extra_args: list[str]          # RSS追加引数（例: ["--no-filter"]）（案A用）
    build_prompt: Callable[[str, str], str]  # (agent, base_date) -> prompt
    resolve_notify_path: Callable[[str, str], Path | None]  # 通知ファイルパス解決（動的分岐用）
    pre_agent_hook: Callable[[str, str], str | None] | None   # エージェント実行前フック（スキップ時はNone返却）
    post_agents_hook: Callable[[str], None] | None            # 全エージェント実行後の追加ステップ
    post_notify_hook: Callable[[str], None] | None            # 通知後の追加ステップ
```

#### 4. 共通runner関数

```python
def run_pipeline(config: PipelineConfig) -> None:
    """パイプラインの共通実行フロー"""
    # 1. オプション解析
    # 2. 環境準備（caffeinate, load_env, SLACK_BOT_TOKEN設定）
    # 3. ログローテーション
    # 4. ジョブファイル生成（Step 0）
    # 5. RSSフィード事前取得（Step 1）
    # 6. エージェント実行ループ（Step 2）
    #    - pre_agent_hook でスキップ判定
    #    - build_prompt でプロンプト構築
    # 7. post_agents_hook（Step 2.5等）
    # 8. 親タスク完了処理（Step 3）
    # 9. Slack通知（Step 4）
    #    - resolve_notify_path で通知ファイルパス解決
    # 10. post_notify_hook（Step 5等）
    # 11. 完了サマリー
    # 12. caffeinate解除
```

### 各パイプラインファイルに残すもの

#### run-daily-pipeline.py

- `AGENTS` リスト
- `NOTIFY_FILE_MAP`
- `LIFESTYLE_THEME_MAP`（曜日テーマ）
- `default_base_date`: 昨日を返す関数
- `rss_categories`: `["tech", "biz_car", "academic", "lifestyle_events"]`
- `build_prompt`: lifestyle-event-scout のみ当日基準日に差し替えるロジック
- `resolve_notify_path`: lifestyle-event-scout の曜日テーマ動的解決
- `pre_agent_hook`: None（全エージェント通常実行）
- `post_agents_hook`: None
- `post_notify_hook`: None

#### run-weekly-pipeline.py

- `AGENTS` リスト
- `NOTIFY_FILE_MAP`
- `WEEKLY_PIPELINE_MODE_AGENTS` セット
- `default_base_date`: 当日を返す関数
- `rss_categories`: `["tech_events", "lifestyle_events"]`
- `rss_extra_args`: `["--no-filter"]`
- `build_prompt`: WEEKLY_PIPELINE_MODE_AGENTS に応じた「週次パイプラインモード」付きプロンプト
- `resolve_notify_path`: None（静的マップのみ）
- `pre_agent_hook`: tech-poc-planner をスキップする判定
- `post_agents_hook`: `run_poc_planner()`
- `post_notify_hook`: `run_freshness_check()`
- `run_poc_planner()` / `run_freshness_check()` / `check_freshness()` はweekly固有関数として残す

## 修正対象

- `scripts/_pipeline_common.py`（新規作成）
- `scripts/run-daily-pipeline.py`（共通部分を削除、import + config定義に書き換え）
- `scripts/run-weekly-pipeline.py`（共通部分を削除、import + config定義に書き換え）

## タスク分解

### Task 1: _pipeline_common.py 作成

- **対象ファイル:** `scripts/_pipeline_common.py`
- **変更内容:**
  - PipelineConfig dataclass 定義
  - ユーティリティ関数群の移動
  - ヘルパー関数群の移動
  - `run_pipeline()` 共通runner関数の実装

### Task 2: run-daily-pipeline.py リファクタリング

- **対象ファイル:** `scripts/run-daily-pipeline.py`
- **変更内容:**
  - 共通関数を `_pipeline_common` からimport
  - PipelineConfig を構築して `run_pipeline()` に渡す形に書き換え
  - daily固有ロジック（lifestyle曜日テーマ等）をコールバック関数として定義

### Task 3: run-weekly-pipeline.py リファクタリング

- **対象ファイル:** `scripts/run-weekly-pipeline.py`
- **変更内容:**
  - 共通関数を `_pipeline_common` からimport
  - PipelineConfig を構築して `run_pipeline()` に渡す形に書き換え
  - weekly固有ロジック（poc-planner, freshness check等）をコールバック関数として定義

### Task 4: 動作確認

- **変更内容:**
  - `python3.12 scripts/run-daily-pipeline.py --no-job-file 2026-05-10` でdryrun的に起動確認
  - `python3.12 scripts/run-weekly-pipeline.py --no-job-file 2026-05-11` でdryrun的に起動確認
  - import エラー、型エラーがないことを確認

## 影響範囲

- launchd から呼び出される `run-daily-pipeline.py` / `run-weekly-pipeline.py` のエントリーポイント（`if __name__ == "__main__"` ブロック）は変更なし
- 外部から呼ばれるインターフェース（コマンドライン引数）は変更なし
- `_version_check` の import は各パイプラインファイルに残す

## テスト計画

- [ ] `python3.12 -c "from _pipeline_common import run_pipeline, PipelineConfig"` が成功する
- [ ] `python3.12 scripts/run-daily-pipeline.py --help` 相当の起動が従来と同じ出力を返す（--no-job-file で軽量確認）
- [ ] `python3.12 scripts/run-weekly-pipeline.py --help` 相当の起動が従来と同じ出力を返す
- [ ] 既存の launchd plist からの呼び出しパスに変更がないことを確認

## 設計上の判断メモ

- **なぜクラス継承ではなくCallableベースか:** スクリプト300行規模で継承階層を作ると、デバッグ時にどこのメソッドが呼ばれているか追いにくい。Callableなら各pipelineファイル内で定義が完結し、grepで追える。
- **なぜdataclassか:** TypedDictでも可だが、dataclassの方がデフォルト値やOptionalの表現が自然。
- **RSSのfeed_date差し替え（daily: lifestyle_eventsのみ当日）:** `build_prompt` ではなくRSS取得フェーズの差分。`rss_categories` に加えて `rss_date_override: Callable[[str, str], str] | None` を追加するか、RSS取得自体をフック化するか要検討。→ シンプルに `rss_fetch_hook: Callable[[str, Path], None] | None` として、RSS取得ステップ全体を各pipelineが定義する方式が良い。
