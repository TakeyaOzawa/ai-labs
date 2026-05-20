# WSL2 セットアップ手順

## 前提条件
- Windows 11 + WSL2 (Ubuntu 26.04 LTS)
- Docker Desktop for Windows (WSL2バックエンド)
- Python 3.12

## 1. crontab 設定

```bash
crontab -e
# 以下を追加:
0 6 * * * /usr/bin/python3.12 /home/$USER/scripts/pipelines/run-radio-content-pipeline.py >> /home/$USER/logs/jobs/radio_content_pipeline/cron.log 2>&1
```

## 2. systemd user service 設定

```bash
mkdir -p ~/.config/systemd/user
cp docs/wsl2-radio-pipeline-watcher.service ~/.config/systemd/user/radio-pipeline-watcher.service

# サービス有効化
systemctl --user daemon-reload
systemctl --user enable radio-pipeline-watcher
systemctl --user start radio-pipeline-watcher

# 状態確認
systemctl --user status radio-pipeline-watcher
```

## 3. ログディレクトリ作成

```bash
mkdir -p ~/logs/jobs/radio_content_pipeline
mkdir -p ~/logs/jobs/radio_content_pipeline_watcher
```

## 4. Docker Compose ビルド

```bash
cd ~/tools/radio_content_pipeline
docker compose build
```
