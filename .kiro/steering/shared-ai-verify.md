---
inclusion: fileMatch
fileMatchPattern: [".shared-ai/rules/**/*.md", ".shared-ai/rules/*.md", ".shared-ai/lookups/*.md", ".shared-ai/references/*-guide.md"]
description: .shared-ai配下の階層構造変更時に、構造検証スクリプトとスモークテストの実行を促す
---

# .shared-ai 構造変更時の検証

`.shared-ai/` 配下のルール・lookups・references を変更しました。
以下の検証を実施してください。

## 必須: 静的構造検証（軽量）

変更完了後、以下を実行して全チェック PASS を確認すること:

```bash
python3.12 ~/scripts/setup/verify-shared-ai-structure.py --quick
```

## 推奨: フル検証（手動実行時）

コミット前やパス変更を伴う大きな変更の場合は、フル検証を推奨:

```bash
python3.12 ~/scripts/setup/verify-shared-ai-structure.py
```

## 推奨: スモークテスト

構造変更（ファイル移動・パス変更・パターン変更）を伴う場合、
変更に関連する項目のスモークテストを実施すること:

- `~/.shared-ai/references/ai-rule-smoketest-guide.md`
