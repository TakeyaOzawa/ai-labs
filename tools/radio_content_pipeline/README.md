# Radio Content Pipeline

ラジオ録音→文字起こし→要約パイプライン（日次運用版）

## アーキテクチャ

- スポット起動方式（常時稼働コンテナなし）
- ホスト側 cron/LaunchAgent でスケジュール管理
- ファイルウォッチャーによるイベント駆動処理

## セットアップ

### 1. Docker イメージビルド

```bash
cd ~/tools/radio_content_pipeline
docker compose build
```

### 2. 環境変数

`.env` を作成（`.env.example` を参考）:

```bash
cp .env.example .env
# SLACK_WEBHOOK_URL を設定
```

### 3. 動作検証

```bash
# パイプラインスクリプトの dry-run（Docker不要）
python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py --dry-run

# 番組検索（radiko API疎通確認）
docker compose run --rm recorder python3 src/main.py --run-now

# 結果確認
cat state/recording-tasks.json | python3.12 -m json.tool

# ウォッチャーの動作確認（1回スキャンして終了）
python3.12 ~/scripts/jobs/radio-pipeline-watcher.py --once
```

### 4. LaunchAgent 登録（macOS）

```bash
launchctl load ~/Library/LaunchAgents/com.user.radio-pipeline.plist
launchctl load ~/Library/LaunchAgents/com.user.radio-pipeline-watcher.plist

# 確認
launchctl list | grep radio-pipeline
```

## 番組リストの設定

### 放送局の検索

```bash
cd ~/tools/radio_content_pipeline

# 利用可能な放送局一覧
docker compose run --rm recorder python3 src/program_resolver.py stations
```

出力例:
```
TBS             TBSラジオ
QRR             文化放送
LFR             ニッポン放送
FMT             TOKYO FM
FMJ             J-WAVE
...
```

### 番組の検索

```bash
# 特定局の全番組を表示
docker compose run --rm recorder python3 src/program_resolver.py search -s TBS

# キーワードで検索（全局対象）
docker compose run --rm recorder python3 src/program_resolver.py search "オールナイト"

# 特定局 + キーワード
docker compose run --rm recorder python3 src/program_resolver.py search -s LFR "オールナイト"
```

出力例:
```
局ID       番組名                               曜日時間             出演者
──────────────────────────────────────────────────────────────────────────────────────────
  LFR      オードリーのオールナイトニッポン       土 25:00             オードリー
  LFR      佐久間宣行のオールナイトニッポン0(ZERO) 水 27:00            佐久間宣行
```

### config/programs.yml の設定

```yaml
programs:
  # 基本: 番組名で指定
  - name: "オードリーのオールナイトニッポン"
    station_id: LFR
    source: radiko

  # 出演者で絞り込み（番組名が変わっても追従可能）
  - performer_contains: "超特急"
    station_id: QRR
    source: radiko

  # 番組名 + 出演者の両方で絞り込み（AND条件）
  - name: "オールナイトニッポン"
    station_id: LFR
    source: radiko
    performer_contains: "佐久間宣行"

  # 特定曜日のみ（0=月, 1=火, ..., 6=日）
  - name: "佐久間宣行のオールナイトニッポン0(ZERO)"
    station_id: LFR
    source: radiko
    day_of_week: 2  # 水曜のみ
```

**フィールド一覧:**

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `station_id` | ✅ | 放送局ID（`stations` コマンドで確認） |
| `source` | — | `radiko`（デフォルト） |
| `name` | ※ | 番組名の部分一致キーワード |
| `performer_contains` | ※ | 出演者名の部分一致キーワード |
| `day_of_week` | — | 曜日フィルタ（0=月〜6=日） |

※ `name` と `performer_contains` のいずれか1つ以上が必須

### 設定変更後の確認

```bash
# 設定した番組が正しく検出されるか確認（録音はしない）
docker compose run --rm recorder python3 src/main.py --run-now

# タスクリストをリセットしたい場合
rm state/recording-tasks.json
```

## 日次運用

### 手動実行

```bash
# 番組検索 + 録音（文字起こし以降はウォッチャーに委譲）
python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py

# ジョブファイルなしで実行
python3.12 ~/scripts/pipelines/run-radio-content-pipeline.py --no-job-file
```

### 個別コマンド

```bash
cd ~/tools/radio_content_pipeline

# 番組検索のみ
docker compose run --rm recorder python3 src/main.py --run-now

# 録音のみ（pendingタスクを全件処理）
docker compose run --rm recorder python3 src/recorder.py --once

# 文字起こし（ファイル指定）
docker compose run --rm transcriber python3 src/transcriber.py --file /data/recordings/<ファイル名>.m4a

# 文字起こし（pendingタスクを全件処理）
docker compose run --rm transcriber python3 src/transcriber.py --once
```

## ファイル構成

```
~/tools/radio_content_pipeline/
├── config/programs.yml     # 録音対象番組リスト
├── data/
│   ├── recordings/         # 録音ファイル（M4A）
│   ├── transcripts/        # 文字起こし結果（JSON）
│   └── summaries/          # 要約（Markdown）
├── state/                  # タスク状態ファイル
├── src/                    # Pythonソース
├── recorder/Dockerfile
├── transcriber/Dockerfile
└── docker-compose.yml

~/Documents/works/scout_reports/radio_contents/
├── {局名}_{番組名}/
│   ├── YYYYMMDD_*_summary.md   # 要約（無期限保持）
│   └── tmp/                     # 音声+JSON（5件ローテーション）
```
