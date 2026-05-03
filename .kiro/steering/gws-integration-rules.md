---
inclusion: always
---

# GWS連携ルール

## GWS CLIを優先使用

Gmail・Google Drive・Google Calendar・Google Docs・Google Sheets・Google Chat・Google Meet・Google Tasks・Google Forms・Google Slidesなど、Google Workspaceサービスへの操作依頼を受けた場合は、以下の手順で対応すること。

### 優先順位

1. `~/.kiro/skills/` 配下の `gws-*` スキル（gws-gmail / gws-drive / gws-calendar / gws-docs / gws-sheets / gws-chat / gws-meet / gws-tasks / gws-forms / gws-slides 等）を確認し、対応するスキルがあればそれを使う
2. スキルが見つからない場合のみ、MCP直接呼び出しやその他の手段を検討する

### 認証情報

- GWS CLIの認証は `gws auth setup` で設定済み
- 追加の認証設定は不要

### スキルの使い方

- 各スキルの `SKILL.md` に記載されたコマンド形式に従う
- 不明な場合は `gws <service> --help` や `gws schema <service>.<resource>.<method>` で確認する
- ヘルパーコマンド（`+send`, `+agenda` 等）がある場合はそちらを優先的に使用する
