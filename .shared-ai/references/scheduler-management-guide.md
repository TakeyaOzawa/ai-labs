# スケジューラ管理ガイド

## 原則

**`launchctl` を直接使用しない。** 代わりに `manage-scheduler.py` を使用する。

```bash
# ✅ 正しい
python3.12 ~/scripts/jobs/manage-scheduler.py load radio-pipeline
python3.12 ~/scripts/jobs/manage-scheduler.py reload scout-daily-pipeline

# ❌ 禁止
launchctl load ~/Library/LaunchAgents/com.user.radio-pipeline.plist
```

## manage-scheduler.py

### 使い方

```bash
python3.12 ~/scripts/jobs/manage-scheduler.py <action> [label]
```

### アクション

| action | 説明 |
|--------|------|
| `load` | LaunchAgent を登録（起動） |
| `unload` | LaunchAgent を解除（停止） |
| `reload` | unload → load を連続実行 |
| `status` | 登録状態を確認 |
| `list` | 全 com.user.* ジョブを一覧表示 |

### ラベル指定

- ドットなし → `com.user.` プレフィックスが自動付与
- ドットあり → フルラベルとして扱う

```bash
# 以下は同等
python3.12 ~/scripts/jobs/manage-scheduler.py load radio-pipeline
python3.12 ~/scripts/jobs/manage-scheduler.py load com.user.radio-pipeline
```

### 登録済みジョブ一覧

| ラベル（短縮） | 用途 |
|---|---|
| `radio-pipeline` | ラジオ録音パイプライン（毎朝6時） |
| `radio-pipeline-watcher` | ラジオパイプラインウォッチャー（常駐） |
| `scout-daily-pipeline` | 日次scoutパイプライン（毎朝2時） |
| `scout-weekly-pipeline` | 週次scoutパイプライン（土曜3:30） |
| `slack-dispatch-router` | Slackディスパッチルーター（常駐） |

### 典型的な操作

```bash
# 新規登録
python3.12 ~/scripts/jobs/manage-scheduler.py load radio-pipeline

# 設定変更後の再読み込み
python3.12 ~/scripts/jobs/manage-scheduler.py reload radio-pipeline

# 一時停止
python3.12 ~/scripts/jobs/manage-scheduler.py unload radio-pipeline

# 状態確認
python3.12 ~/scripts/jobs/manage-scheduler.py status radio-pipeline

# 全ジョブ一覧
python3.12 ~/scripts/jobs/manage-scheduler.py list
```

## 関連ファイル

- plist配置先: `~/Library/LaunchAgents/com.user.{label}.plist`
- manage-scheduler.py: `~/scripts/jobs/manage-scheduler.py`
- platform-commands.sh: `~/scripts/platform-commands.sh`（OS抽象化レイヤー）
