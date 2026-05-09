---
inclusion: fileMatch
fileMatchPattern: ".shared-ai/references/*-guide.md"
---

# Reference Guide フォーマット確認

`-guide.md` ファイルの編集中です。以下のフォーマット基準を意識してください。

## 確認事項

1. **タイトル**: H1は日本語で「〜ガイド」で終わっているか
2. **概要**: タイトル直下に1〜2文の概要があるか
3. **構造**: テーブル・コードブロック・チェックリストを活用しているか
4. **サイズ**: 8KB以下か（超える場合は分割を検討）
5. **相互参照**: 他のreferencesへの参照は相対ファイル名（`agent-prompt-guide.md`）で記載しているか

## テンプレート参照

新規作成の場合は `~/.shared-ai/templates/reference-guide.md` を参照すること。
