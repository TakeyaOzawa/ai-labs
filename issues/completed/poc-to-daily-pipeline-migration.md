# PoC → daily パイプライン移行

## 変更種別

feat（新規機能追加）

## 概要

PoC検証リポジトリ（`works/poc-rfriends3/2026-05-18_radio-recording-transcription-pipeline/`）で
動作確認済みのラジオ録音→文字起こしパイプラインを、日次運用パイプラインとして正式に配置する。

**設計方針:**
- schedulerコンテナは不要（ホスト側のcron/LaunchAgentでスケジュール管理）
- recorder/transcriberはスポット起動（タスク完了後に自動停止）
- 常時稼働コンテナはゼロ（必要なときだけ起動→完了→停止）
- macOS（Apple Silicon）とWindows 11（WSL2）の両環境に対応
- PoCリポジトリはそのまま残す

## 問題・背景

### 現状（PoC）
- PoCリポジトリ内で `docker compose up -d` により3コンテナが常時稼働
- schedulerコンテナがAPSchedulerで毎朝6時に番組検索
- recorder/transcriberが常時ポーリングでタスク監視

### 移行の動機
- 常時稼働コンテナはリソース消費が無駄（1日1回の処理に24時間稼働は不要）
- スケジュール管理はホスト側（cron/LaunchAgent）の方が信頼性が高い
- PoCディレクトリ名（`2026-05-18_...`）は恒久運用に不向き
- 要約の自動実行を組み込みたい

## アーキテクチャ（スポット起動 + イベント駆動方式）

```
[ホスト側 cron/LaunchAgent — 毎朝6時]
  │
  ├── Step 1: docker compose run --rm recorder python3 src/main.py --run-now
  │            → 番組検索 → タスク追記
  │
  ├── Step 2: docker compose run --rm recorder python3 src/recorder.py --once
  │            → pendingタスクを全件ダウンロード → 完了後に自動終了
  │
  └── (Step 1,2 完了後、パイプラインスクリプトは終了)

[ホスト側 — 5分おきウォッチャー（常駐 or cron）]
  │
  ├── 新規M4Aファイル検知（data/recordings/ に未処理ファイルあり）
  │    → docker compose run --rm transcriber python3 src/transcriber.py --file <path>
  │    → 1ファイルずつ順次処理（1件完了するたびに次のチェックへ）
  │
  ├── 新規JSONファイル検知（data/transcripts/ に未要約ファイルあり）
  │    → invoke-agent.py --agent radio-transcript-summarizer
  │    → 要約MD出力
  │
  └── 新規summary MD検知（data/summaries/ に未通知ファイルあり）
       → notify-slack.py --file <summary.md>（直接呼び出し）
       → file_organizer.py で最終配置先に移動 + ローテーション

※ 各ステップは独立してイベント駆動。1件完了するたびに次の処理が即座にトリガーされる
※ 5分おきのポーリングで未処理ファイルを検知（inotify不使用、OS非依存）
```

### フロー詳細

```
06:00  cron起動 → Step 1 (番組検索: 5秒) → Step 2 (録音開始)
06:06  番組A録音完了 → ウォッチャーが検知 → transcriber起動(番組A)
06:11  番組B録音完了 → ウォッチャーが検知 → transcriber起動待ち(番組Aの完了後)
06:22  番組A文字起こし完了 → ウォッチャーが検知 → 要約実行(番組A) + transcriber起動(番組B)
06:25  番組A要約完了 → Slack通知 + ファイル配置
06:47  番組B文字起こし完了 → 要約実行(番組B)
06:50  番組B要約完了 → Slack通知 + ファイル配置
```

## 出力ディレクトリ構成

```
~/Documents/works/scout_reports/radio_contents/
├── TBS_空気階段の踊り場/
│   ├── 20260519_TBS_空気階段の踊り場_summary.md    ← 要約（本体）
│   ├── 20260518_TBS_空気階段の踊り場_summary.md
│   └── tmp/                                        ← 音声+生文字起こし（5件ローテーション）
│       ├── 20260519_TBS_空気階段の踊り場.m4a
│       ├── 20260519_TBS_空気階段の踊り場.json
│       ├── 20260518_TBS_空気階段の踊り場.m4a
│       └── 20260518_TBS_空気階段の踊り場.json
│
├── LFR_オードリーのオールナイトニッポン/
│   ├── 20260517_LFR_オードリーのオールナイトニッポン_summary.md
│   └── tmp/
│       ├── 20260517_LFR_オードリーのオールナイトニッポン.m4a
│       └── 20260517_LFR_オードリーのオールナイトニッポン.json
│
└── ...（番組ごとにディレクトリ）
```

### ファイル命名規則

| 種別 | パス | ローテーション |
|------|------|--------------|
| 要約MD | `{番組dir}/YYYYMMDD_{局名}_{番組名}_summary.md` | なし（無期限保持） |
| 音声M4A | `{番組dir}/tmp/YYYYMMDD_{局名}_{番組名}.m4a` | 5件保持、古い順に削除 |
| 文字起こしJSON | `{番組dir}/tmp/YYYYMMDD_{局名}_{番組名}.json` | 5件保持、古い順に削除 |

### ローテーションルール

- `tmp/` 配下のファイルは番組ごとに最新5回分を保持
- 6件目が追加されたら最も古い1件（.m4a + .json のペア）を削除
- 要約MDは `tmp/` の外に配置し、削除しない（ナレッジとして蓄積）

## 修正対象

### 新規作成
- `~/tools/radio_content_pipeline/` — 正式配置先ディレクトリ
- `~/Documents/works/scout_reports/radio_contents/` — 出力先ディレクトリ
- `~/scripts/jobs/radio-pipeline.py` — 日次録音トリガー（Step 1-2）
- `~/scripts/jobs/radio-pipeline-watcher.py` — ファイルウォッチャー（文字起こし→要約→通知）
- `src/file_organizer.py` — ファイル配置・ローテーション管理モジュール
- macOS: `~/Library/LaunchAgents/com.user.radio-pipeline.plist`, `com.user.radio-pipeline-watcher.plist`
- WSL2: crontab + `~/.config/systemd/user/radio-pipeline-watcher.service`

### 既存修正（PoC → daily移植時）
- `docker-compose.yml` — schedulerサービス削除、`restart: unless-stopped` 削除
- `src/recorder.py` — `--once` モードの強化（全pendingタスク処理後に確実に終了）
- `src/transcriber.py` — `--once` モードの強化（同上）

### 移行対象（PoCからコピー）
- `src/` — 全Pythonモジュール（main.py含む、scheduler機能は使わない）
- `config/` — programs.yml, pipeline.yml
- `data/` — recordings, transcripts, summaries
- `recorder/Dockerfile`, `transcriber/Dockerfile`
- `.env`
- `.kiro/agents/radio-transcript-summarizer.md`

## タスク分解

### Task 1: 正式配置先の作成 ✅

- **対象:** `~/tools/radio_content_pipeline/`
- **変更内容:**
  - PoCディレクトリから必要ファイルをコピー
  - 不要ファイルの除外（results/, issues/, rfriends3/, .devcontainer/, state/）
  - docker-compose.ymlからschedulerサービスを削除
  - `restart: unless-stopped` を削除（スポット起動のため不要）
  - git init で新規リポジトリ化
  - PoCディレクトリはそのまま残す

### Task 2: docker-compose.yml のスポット起動対応 ✅

- **対象:** `~/tools/radio_content_pipeline/docker-compose.yml`
- **変更内容:**
  - schedulerサービスを削除
  - recorder/transcriberから `restart`, `command` を削除（`docker compose run` で都度指定）
  - ボリュームマウントはそのまま維持
  - `state/` ディレクトリのマウント追加（スポット実行間で状態を共有）

```yaml
services:
  recorder:
    build:
      context: .
      dockerfile: recorder/Dockerfile
    volumes:
      - ./config:/app/config:ro
      - ./state:/app/state
      - ./data/recordings:/data/recordings
      - ./data/transcripts:/data/transcripts
      - ./src:/app/src:ro
    environment:
      - TZ=Asia/Tokyo
      - PYTHONPATH=/app/src
      - PYTHONUNBUFFERED=1
    working_dir: /app

  transcriber:
    build:
      context: .
      dockerfile: transcriber/Dockerfile
    volumes:
      - ./config:/app/config:ro
      - ./state:/app/state
      - ./data/recordings:/data/recordings
      - ./data/transcripts:/data/transcripts
      - ./data/summaries:/data/summaries
      - ./src:/app/src:ro
      - whisper-cache:/root/.cache/huggingface
    environment:
      - TZ=Asia/Tokyo
      - WHISPER_MODEL=small
      - WHISPER_BEAM_SIZE=1
      - WHISPER_VAD_FILTER=false
      - WHISPER_LANGUAGE=ja
      - WHISPER_COMPUTE_TYPE=int8
      - PYTHONPATH=/app/src
      - PYTHONUNBUFFERED=1
    working_dir: /app

volumes:
  whisper-cache:
    driver: local
```

### Task 3: 日次パイプライン実行スクリプト（録音トリガー） ✅

- **対象:** `~/scripts/jobs/radio-pipeline.py`
- **変更内容:**
  - `config.load_env()` で環境変数ロード
  - `start_caffeinate()` / `stop_caffeinate()` でスリープ防止
  - `PipelineLogger` でログ管理
  - Step 1（番組検索）+ Step 2（録音）を順次実行
  - ジョブファイル自動生成（番組検索結果に基づき子ジョブを動的追加）
  - 録音完了後にスクリプトは終了（文字起こし以降はウォッチャーに委譲）
  - 失敗時はSlack通知（`notify-slack.py --text "..."` 直接呼び出し）
  - `--dry-run` オプション（実行せずに計画を表示）
  - 実行ログを `~/logs/jobs/radio-pipeline/` に出力

### Task 4: ファイルウォッチャースクリプト（イベント駆動） ✅

- **対象:** `~/scripts/jobs/radio-pipeline-watcher.py`
- **変更内容:**
  - 5分おきにポーリング（OS非依存、inotify不使用）
  - 検知対象と処理:

| 検知条件 | アクション |
|---------|-----------|
| `data/recordings/` に新規M4A（対応JSONなし） | `docker compose run --rm transcriber python3 src/transcriber.py --file <path>` |
| `data/transcripts/` に新規JSON（対応_summary.mdなし） | `invoke-agent.py --agent radio-transcript-summarizer` |
| `data/summaries/` に新規MD（未通知） | `notify-slack.py --file <path>` + `file_organizer.py` |

  - 1件ずつ順次処理（並行実行しない。transcriberはCPU負荷が高いため）
  - ジョブファイルベースの状態管理（既存のfind-job.py / update-job.pyと同じ方式）
  - `--once` モード（1回スキャンして終了）と `--watch` モード（5分おきポーリング常駐）
  - 実行ログを `~/logs/jobs/radio-pipeline-watcher/` に出力

#### 処理中フラグ: ジョブファイル方式（既存Step拡張）

既存パイプライン（scout_daily等）と同じ `~/Documents/works/jobs/` 配下のJSONジョブファイルで管理する。
`find-job.py` / `update-job.py` をそのまま利用し、radio-pipeline用のパイプライン名を追加する。

**ジョブファイル配置:**
```
~/Documents/works/jobs/radio_pipeline/
└── 2026-05-19_xxxx_radio_pipeline.json
```

**ジョブファイル構造（親 + 子ジョブ）:**
```json
{
  "job_id": "0019e...",
  "job_name": "radio_pipeline",
  "status": "running",
  "started_at": "2026-05-19T06:00:00+09:00",
  "updated_at": "2026-05-19T06:22:00+09:00",
  "completed_at": null,
  "child_jobs": [
    {
      "job_id": "0019e...-001",
      "job_name": "recording",
      "status": "completed",
      "args": {"program": "空気階段の踊り場", "station": "TBS"},
      "started_at": "2026-05-19T06:00:05+09:00",
      "completed_at": "2026-05-19T06:06:00+09:00"
    },
    {
      "job_id": "0019e...-002",
      "job_name": "transcription",
      "status": "running",
      "args": {"file": "TBS_空気階段の踊り場_20260519.m4a"},
      "started_at": "2026-05-19T06:06:30+09:00",
      "completed_at": null
    },
    {
      "job_id": "0019e...-003",
      "job_name": "summarization",
      "status": "pending",
      "args": {"file": "TBS_空気階段の踊り場_20260519.json"},
      "started_at": null,
      "completed_at": null
    },
    {
      "job_id": "0019e...-004",
      "job_name": "notification",
      "status": "pending",
      "args": {"file": "TBS_空気階段の踊り場_20260519_summary.md"},
      "started_at": null,
      "completed_at": null
    }
  ]
}
```

**ステータス遷移:**
```
pending → running → completed
                  → failed
```

**ウォッチャーの判定ロジック:**
1. ジョブファイルを `find-job.py --pipeline radio_pipeline --status pending` で検索
2. pendingの子ジョブがあれば、その `job_name` に応じた処理を実行:
   - `recording`: 録音トリガー（Step 1-2）で作成済み。ウォッチャーでは扱わない
   - `transcription`: `docker compose run --rm transcriber ...` を実行
   - `summarization`: `invoke-agent.py --agent radio-transcript-summarizer` を実行
   - `notification`: `notify-slack.py --file <path>` + `file_organizer.py` を実行
3. 実行開始時に `update-job.py --set '{"status": "running"}'` で更新
4. 完了時に `update-job.py --set '{"status": "completed"}'` で更新
5. 失敗時に `update-job.py --set '{"status": "failed", "error": "..."}'` で更新

**二重起動防止:**
- ウォッチャーは `find-job.py --status running` で実行中ジョブを確認
- `running` の子ジョブが存在する場合、同種の新規ジョブは起動しない（前回の完了を待つ）
- タイムアウト: `running` が2時間以上経過した場合は `failed` に更新し、次回ポーリングでリトライ可能にする

**録音トリガー（radio-pipeline.py）との連携:**
- `radio-pipeline.py`（Step 1-2）が実行されると:
  1. 新規ジョブファイルを作成（親ジョブ: `radio_pipeline`）
  2. 番組検索結果に基づき、各番組の子ジョブを `recording` → `transcription` → `summarization` → `notification` の4段階で追加
  3. `recording` を `running` に更新して録音実行
  4. 録音完了後に `recording` を `completed`、`transcription` を `pending` に更新
  5. 以降はウォッチャーが `pending` を検知して順次処理

### Task 5a: macOS定期実行設定（LaunchAgent） ✅

- **対象:**
  - `~/Library/LaunchAgents/com.user.radio-pipeline.plist` — 毎朝6時の録音トリガー
  - `~/Library/LaunchAgents/com.user.radio-pipeline-watcher.plist` — ウォッチャー常駐
- **変更内容:**
  - 録音トリガー: StartCalendarInterval で毎朝6時に `radio-pipeline.py` を実行
  - ウォッチャー: KeepAlive: true で `radio-pipeline-watcher.py --watch` を常駐化

### Task 5b: WSL2定期実行設定（crontab + systemd） ✅

- **対象:**
  - crontab — 毎朝6時の録音トリガー
  - `~/.config/systemd/user/radio-pipeline-watcher.service` — ウォッチャー常駐
- **変更内容:**
  - 録音トリガー: `0 6 * * * python3.12 ~/scripts/jobs/radio-pipeline.py`
  - ウォッチャー: systemd user serviceで `radio-pipeline-watcher.py --watch` を常駐化

```ini
# ~/.config/systemd/user/radio-pipeline-watcher.service
[Unit]
Description=Radio Pipeline File Watcher
After=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3.12 %h/scripts/jobs/radio-pipeline-watcher.py --watch
Restart=always
RestartSec=30
Environment=HOME=%h

[Install]
WantedBy=default.target
```

### Task 6: recorder/transcriberの--onceモード強化 ✅

- **対象:** `src/recorder.py`, `src/transcriber.py`
- **変更内容:**
  - `--once` で全pendingタスクを処理し、pendingが0になったら確実に終了
  - 処理結果のサマリーをJSON形式で標準出力に出力（パイプラインスクリプトが結果を取得可能に）
  - 終了コード: 0=全成功、1=一部失敗

### Task 7: ファイル配置・ローテーション（file_organizer.py） ✅

- **対象:** `src/file_organizer.py`
- **変更内容:**
  - 録音完了後: M4Aを `scout_reports/radio_contents/{局名}_{番組名}/tmp/YYYYMMDD_{局名}_{番組名}.m4a` に配置
  - 文字起こし完了後: JSONを同 `tmp/` 配下に配置
  - 要約完了後: MDを `scout_reports/radio_contents/{局名}_{番組名}/YYYYMMDD_{局名}_{番組名}_summary.md` に配置
  - ローテーション: `tmp/` 配下のファイルが5件を超えたら古い順に削除（.m4a + .json ペア）
  - 番組ディレクトリの自動作成（初回実行時）
  - パイプラインスクリプト（radio-pipeline.py）の各Step完了後に呼び出し

### Task 8: データ保持・クリーンアップ ✅

- **変更内容:**
  - `data/recordings/` の保持期間（30日）のクリーンアップをパイプラインスクリプトに組み込み
  - `data/transcripts/`, `data/summaries/` は無期限保持
  - パイプライン実行の最後にクリーンアップを実行

## macOS / WSL2 環境差異まとめ

| 項目 | macOS (Apple Silicon) | Windows 11 (WSL2) |
|------|----------------------|-------------------|
| CPU | ARM64 | x86_64 |
| Docker | Docker Desktop for Mac | Docker Desktop for Windows (WSL2バックエンド) |
| コンテナ動作 | 同一docker-compose.yml | 同一docker-compose.yml |
| faster-whisper性能 | RTF 0.21-0.27x (int8) | RTF 0.1-0.2x想定 (AVX2最適化) |
| ホスト側Python | python3.12 (Homebrew) | python3.12 (apt / pyenv) |
| 定期実行 | LaunchAgent (StartCalendarInterval) | crontab |
| プロジェクト配置 | `~/tools/radio_content_pipeline/` | `~/tools/radio_content_pipeline/` (WSL2内) |
| invoke-agent.py | ホスト側で実行 | WSL2内で実行 |

## 影響範囲

- PoCディレクトリはそのまま残す（変更なし）
- 新規ディレクトリ `~/tools/radio_content_pipeline/` を作成
- ホスト側に日次実行スクリプトとスケジュール設定を追加
- 常時稼働コンテナなし（Docker Desktopのリソース消費を最小化）

## テスト計画

### 共通（macOS / WSL2）
- [ ] 新配置先で `docker compose build` が成功すること
- [ ] `docker compose run --rm recorder python3 src/main.py --run-now` で番組検索が動作すること
- [ ] `docker compose run --rm recorder python3 src/recorder.py --once` で録音→終了すること
- [ ] ウォッチャーが新規M4Aを検知してtranscriberを起動すること
- [ ] 1件の文字起こし完了後、即座に要約が開始されること
- [ ] 要約MD出力後、即座にSlack通知が送信されること
- [ ] file_organizer.pyで最終配置先に正しく配置されること
- [ ] tmp/配下が5件を超えた場合に古いファイルが削除されること
- [ ] 実行後にコンテナが残っていないこと（`docker compose ps` が空）
- [ ] ウォッチャーの二重起動が防止されること

### macOS固有
- [ ] LaunchAgentが毎朝6時に録音トリガーを起動すること
- [ ] ウォッチャーがKeepAliveで常駐していること
- [ ] `launchctl list | grep radio-pipeline` でサービスが表示されること

### WSL2固有
- [ ] crontabが毎朝6時に録音トリガーを起動すること
- [ ] systemd serviceでウォッチャーが常駐していること
- [ ] `systemctl --user status radio-pipeline-watcher` でactive (running)であること
- [ ] WSL2内のext4パスでのファイルI/Oが正常であること

## 前提条件・制約

- schedulerコンテナは使用しない（ホスト側でスケジュール管理）
- コンテナはスポット起動（`docker compose run --rm`）、常時稼働なし
- macOS: Docker Desktop for Mac (Apple Silicon)、Python 3.12 (Homebrew)
- WSL2: Docker Desktop for Windows (WSL2バックエンド)、Ubuntu 26.04 LTS、Python 3.12
- invoke-agent.pyはホスト側で実行（Docker内からは呼べない）
- WSL2ではプロジェクトをWSL2内のホームディレクトリに配置
- PoCリポジトリはそのまま残す

## 既存パイプラインとの整合性

### 統一する方針

既存パイプライン（scout_daily等）と以下の点を統一する:

| 項目 | 既存方式 | radio-pipelineでの採用 |
|------|---------|----------------------|
| LaunchAgent起動 | `/bin/zsh -l -c "python3.12 ..."` | ✅ 同じ方式（環境変数ロード確保） |
| 環境変数ロード | `config.load_env()` → `platform-commands.sh source-env` | ✅ 同じ方式 |
| caffeinate | `start_caffeinate()` / `stop_caffeinate()` | ✅ 録音トリガー実行中に適用 |
| Slack通知 | `notify-slack.py` 直接呼び出し | ✅ 同じ方式（固定テキスト通知） |
| ジョブファイル | `~/Documents/works/jobs/` 配下 | ✅ 同じ方式 |
| ログ管理 | `PipelineLogger` | ✅ 同じ方式 |
| AI実行 | `invoke-agent.py` 経由 | ✅ 要約ステップのみ（summarization） |

### 既存と異なる点（意図的な差異）

| 項目 | 既存方式 | radio-pipeline | 理由 |
|------|---------|---------------|------|
| 実行モデル | 同期逐次（1プロセスで全完了） | イベント駆動（録音トリガー + ウォッチャー） | 録音+文字起こしに40分以上かかるため、完了を待たずに次の処理を開始 |
| 常駐プロセス | なし | ウォッチャー（KeepAlive） | ファイル検知ベースのイベント駆動に必要 |
| Docker利用 | なし（ホスト直接実行） | `docker compose run --rm` | radiko認証+faster-whisperの環境分離 |
| ジョブ作成 | 起動時に全ステップ一括生成 | 番組検索結果に基づき動的生成 | 番組数が日によって変動するため |

### Slack通知方式の決定

- **固定テキスト通知（録音完了、文字起こし完了、エラー）**: `notify-slack.py` 直接呼び出し
- **要約内容を含む通知**: `notify-slack.py --file <summary.md>` で要約MDを投稿
- **slack-notifyエージェントは不使用**: 通知テキストが固定的なため、AIエージェント経由は不要

### caffeinate の適用範囲

- **録音トリガー（radio-pipeline.py）**: `start_caffeinate()` → Step 1-2実行 → `stop_caffeinate()`
- **ウォッチャー（radio-pipeline-watcher.py）**: 処理実行中のみ caffeinate を有効化（ポーリング待機中は不要）

```python
# ウォッチャーでのcaffeinate使用イメージ
def process_pending_job(job):
    cafe_pid = start_caffeinate()
    try:
        # transcriber実行 or 要約実行
        ...
    finally:
        stop_caffeinate(cafe_pid)
```

## 想定スケジュール

- Task 1: 配置先作成（20分）
- Task 2: docker-compose.yml調整（15分）
- Task 3: 日次パイプラインスクリプト（45分）
- Task 4: 要約実行スクリプト（30分）
- Task 5a: macOS LaunchAgent設定（15分）
- Task 5b: WSL2 crontab設定（10分）
- Task 6: --onceモード強化（20分）
- Task 7: ファイル配置・ローテーション（30分）
- Task 8: クリーンアップ実装（15分）
- 合計: 約200分

## 拡張性

### 生成AI処理のリソース効率

生成AIが処理を担当するステップは **summarization（要約）のみ**。その他は全て非AI処理。

| ステップ | 生成AI | 実行方式 | コンテキスト |
|---------|--------|---------|------------|
| recording | ❌ | Docker run --rm → 終了 | — |
| transcription | ❌ | Docker run --rm → 終了 | — |
| summarization | ✅ | invoke-agent.py → 終了 | full_textのみ（コマンド抽出） |
| notification | ❌ | notify-slack.py → 終了 | — |

設計原則:

| 原則 | 実現方法 |
|------|---------|
| 常駐しない | `invoke-agent.py` で都度起動→処理→終了。ウォッチャー自体はAI不使用 |
| コンテキスト軽量 | JSONを直接readFileせず、`python3.12 -c` でfull_textのみ抽出して入力 |
| 待機しない | 1ファイル処理完了後にプロセス終了。次のファイルは次回ポーリングで検知 |
| 並行しない | 1件ずつ順次処理。LLM APIの同時呼び出しを避ける |

### 外国語コンテンツの日本語翻訳対応

podcast等の外国語ソースを追加し、要約時に日本語翻訳して出力する拡張が可能。

**変更箇所と影響範囲:**

| レイヤー | 変更内容 | 影響範囲 |
|---------|---------|---------|
| `config/programs.yml` | `language` フィールド追加 | 設定ファイルのみ |
| `src/program_resolver.py` | podcast feed対応（source: podcast） | 新規ソース追加 |
| `src/transcriber.py` | `language` パラメータをconfigから取得 | 既存コード小修正 |
| エージェント定義 | 言語判定+翻訳ガイドライン追加 | プロンプト変更のみ |
| ジョブ管理 | 変更なし | — |
| ウォッチャー | 変更なし | — |
| ファイル配置 | 変更なし（同じディレクトリ構造） | — |

**programs.yml 拡張例:**

```yaml
programs:
  - name: "空気階段の踊り場"
    station_id: TBS
    source: radiko
    language: ja

  - name: "Lex Fridman Podcast"
    source: podcast
    feed_url: "https://lexfridman.com/feed/podcast/"
    language: en

  - name: "Huberman Lab"
    source: podcast
    feed_url: "https://feeds.megaphone.fm/hubermanlab"
    language: en
```

**エージェントプロンプト拡張（翻訳対応）:**

```markdown
## 言語対応
- Step 1で取得したメタデータの `language` を確認する
- `language` が `ja` 以外の場合:
  - 要約は日本語に翻訳して出力する
  - 原文の重要なフレーズは括弧内に原語を併記する（例: 「技術的負債（technical debt）」）
  - 固有名詞（人名、サービス名等）は原語表記を維持する
- `language` が `ja` の場合: 従来通り日本語で要約
```

**ジョブ管理への影響:**
- 子ジョブの4段階（recording → transcription → summarization → notification）は言語に依存しない
- `args` フィールドに `language` を含めることで、どの言語で処理されたかを追跡可能

### その他の拡張ポイント

| 拡張 | 対応方針 | 変更規模 |
|------|---------|---------|
| podcast対応 | `source: podcast` + feed_url。recorder内にpodcast downloader追加 | 中（新規モジュール） |
| YouTube対応 | `source: youtube` + channel_url。yt-dlpで対応可能 | 小（既存yt-dlp活用） |
| GPU高速化（WSL2） | docker-compose.ymlにNVIDIA GPU設定追加 | 小（設定変更のみ） |
| 複数要約フォーマット | エージェント定義を複数用意（詳細版/簡潔版） | 小（プロンプト追加） |
| 要約の自動Notion投稿 | notificationステップにNotion API呼び出しを追加 | 中（新規エージェント） |
