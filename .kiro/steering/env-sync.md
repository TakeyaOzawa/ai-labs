---
inclusion: fileMatch
fileMatchPattern: ["**/.zshrc", "**/.bashrc", "**/.shared-ai/prompts/*.md"]
description: 環境変数の追加・変更時に関連ファイルへの同期を促すルール
---

# 環境変数同期ルール

以下のファイルをreadFileで読み込み、その指示に従うこと:
- `~/.shared-ai/rules/critical/env-sync.md`
