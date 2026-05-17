# RefreshDatabase 使用禁止ルール

`tests/**/*Test.php` ファイルの編集時に適用する。

**RefreshDatabase トレイトは使用禁止。** 代わりに `DatabaseTransactions` トレイトを使用すること。

RefreshDatabase が検出された場合は、DatabaseTransactions に自動的に置き換えること。
