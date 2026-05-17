---
inclusion: always
description: fileMatch不発時のフォールバック。ファイルパターンに応じたルール解決スクリプトの実行を促す
---

# ファイルパターン別ルール適用

以下のファイルをreadFileで読み込み、その指示に従うこと:
- `~/.shared-ai/rules/filematch-dispatcher.md`

※ 既にfileMatch steeringで該当ルールが注入済みの場合、重複読み込みは不要。
