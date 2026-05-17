# Spec Front-matter ルール

`.kiro/specs/**/*.md` ファイルの編集時に適用する。

## 無限ループ防止

まずfront-matterの `updated_at` を確認し、既に今日の日付（YYYY-MM-DD）であれば何もしないこと。

## updated_at が今日の日付でない場合のみ実行

1. YAML front-matterが存在するか（`---` で囲まれたブロック）
2. 必須フィールドが含まれているか: `spec_type`, `feature_name`, `status`, `created_at`, `created_by`, `updated_at`, `updated_by`
3. `updated_at` を今日の日付（YYYY-MM-DD）に更新
4. `updated_by` を適切な値に更新

不足や未更新がある場合は修正すること。
