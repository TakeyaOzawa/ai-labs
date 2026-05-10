# prompt-interface-extraction: プロンプトから interfaces/ への出力フォーマット分離

## 変更種別

refactor

## 概要

8KB超のプロンプトから出力フォーマット・入力リソース定義を `interfaces/` に切り出し、プロンプトサイズを8KB以下に削減する。

## 問題・背景

- `agent-prompt-guide.md` のルールではプロンプト8KB超は「コンテキスト枯渇リスク」
- 現在7つのプロンプトが8KB超（最大24KB）
- 出力テンプレート・固定リソース定義がプロンプト内に埋め込まれている

## 修正対象

| ファイル | 現サイズ | 目標 | 切り出し内容 |
|----------|---------|------|-------------|
| `prompts/tech-poc-planner.md` | 24KB | ~8KB | 出力テンプレート（記事骨格 + 検証計画フォーマット） |
| `prompts/notion-trend-scout.md` | 12KB | ~8KB | 出力フォーマット + 既知Notionリソース |
| `prompts/gws-trend-scout-collector.md` | 12KB | ~8KB | 議事録テンプレート |
| `prompts/gws-trend-scout.md` | 12KB | ~8KB | Drive APIクエリ方針 + 議事録テンプレート |
| `prompts/slack-trend-scout-channel.md` | 10KB | ~8KB | 出力フォーマット |
| `prompts/notion-digest-scout.md` | 10KB | ~8KB | 出力フォーマット |
| `prompts/tech-blog-writer.md` | 10KB | ~8KB | 記事構成テンプレート + 品質チェックリスト |

## タスク分解

### Task 1: tech-poc-planner.md（最優先・最大効果）

- **対象ファイル:** `prompts/tech-poc-planner.md`
- **生成ファイル:** `interfaces/tech-poc-planner-output.md`
- **変更内容:** 「出力ルール > 出力ファイルの全体構造」「記事骨格の構成」テンプレート部分を interfaces に切り出し、プロンプトからは readFile 参照に置換

### Task 2: notion-trend-scout.md

- **対象ファイル:** `prompts/notion-trend-scout.md`
- **生成ファイル:** `interfaces/notion-trend-scout-output.md`, `interfaces/notion-trend-scout-resources.md`
- **変更内容:** 出力フォーマット + 「既知のNotionリソース」（DB ID等）を分離

### Task 3: gws-trend-scout.md / gws-trend-scout-collector.md

- **対象ファイル:** `prompts/gws-trend-scout.md`, `prompts/gws-trend-scout-collector.md`
- **生成ファイル:** `interfaces/gws-trend-scout-output.md`
- **変更内容:** 議事録テンプレート・Drive APIクエリ方針を分離（2ファイルで共有）

### Task 4: slack-trend-scout-channel.md

- **対象ファイル:** `prompts/slack-trend-scout-channel.md`
- **生成ファイル:** `interfaces/slack-trend-scout-channel-output.md`
- **変更内容:** 出力フォーマットを分離

### Task 5: notion-digest-scout.md

- **対象ファイル:** `prompts/notion-digest-scout.md`
- **生成ファイル:** `interfaces/notion-digest-scout-output.md`
- **変更内容:** 出力フォーマットを分離

### Task 6: tech-blog-writer.md

- **対象ファイル:** `prompts/tech-blog-writer.md`
- **生成ファイル:** `interfaces/tech-blog-writer-output.md`
- **変更内容:** 記事構成テンプレート + 品質チェックリストを分離

## 影響範囲

- 各エージェントの実行時にreadFileが1回追加される（コンテキスト消費は同等だが、プロンプト初期読み込みが軽くなる）
- kiro-cli経路: プロンプトファイルが軽くなるため、初期コンテキスト消費が改善
- IDE経路: 同上

## テスト計画

- [ ] 各プロンプトが8KB以下になっていること（`wc -c`）
- [ ] 切り出し後のプロンプトで readFile 参照が正しいパスを指していること
- [ ] interfaces/ 内のファイルが元のプロンプトの出力フォーマットと同一内容であること
- [ ] 既存のパイプライン実行（daily/weekly）が正常に動作すること
