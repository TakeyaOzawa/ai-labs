---
inclusion: fileMatch
fileMatchPattern: "tests/**/*Test.php"
---

# RefreshDatabase 使用禁止

テストファイルを編集中です。

**RefreshDatabase トレイトは使用禁止です。** 代わりに `DatabaseTransactions` トレイトを使用してください。

RefreshDatabase が検出された場合は、DatabaseTransactions に自動的に置き換えてください。
