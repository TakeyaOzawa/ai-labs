---
inclusion: fileMatch
fileMatchPattern: "works/poc-something/**/SUMMARY.md"
---

# PoC更新→記事完成チェック

SUMMARY.md が更新されました。以下の手順で処理してください:

## Step 0: マーカー確認

ファイルの先頭1行目に `<!-- READY_FOR_WRITER -->` マーカーが存在するか確認してください。

- マーカーが **存在しない** 場合 → 「検証途中の更新のためスキップしました。記事化の準備ができたら SUMMARY.md の先頭行に `<!-- READY_FOR_WRITER -->` を追加してください。」と表示して終了
- マーカーが **存在する** 場合 → Step 1へ

## Step 1: tech-blog-writer 起動提案

`.shared-ai/prompts/tech-blog-writer.md` をreadFileで読み込み、ワークフローを把握してください。

ユーザーに以下を確認:
1. 更新された検証結果を確認しますか？（SUMMARY.mdの内容を表示）
2. このまま tech-blog-writer で記事を完成（または再生成）させますか？
3. output_format は md / docs のどちらですか？（デフォルト: md）

ユーザーが記事完成を希望した場合:
- SUMMARY.mdのパスからpoc_directoryを特定
- poc_directory名からplanファイルのパスを推定（Documents/works/tech_blog_plans/ 配下で日付+テーマが一致するもの）
- tech-blog-writer のワークフローに従い実行

## Step 2: マーカー除去

完了後、SUMMARY.mdの先頭行から `<!-- READY_FOR_WRITER -->` マーカーを削除してください。
