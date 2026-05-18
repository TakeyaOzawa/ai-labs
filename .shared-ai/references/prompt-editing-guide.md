# エージェントプロンプト編集ガイド

エージェントプロンプト（`.shared-ai/prompts/*.md`）の編集時に適用する判断基準。

## 参照ファイルの読み込み判断

### 新規エージェントプロンプトの作成

以下を全て読み込むこと:
- `.shared-ai/references/agent-creation-guide.md`（命名規則、ファイル構成、チェックリスト）
- `.shared-ai/references/agent-prompt-guide.md`（プロンプト構造、コンテキスト節約）

### 既存プロンプトの構造的変更

以下に該当する場合は `.shared-ai/references/agent-prompt-guide.md` をreadFileで読み込むこと:
- Phase構造の変更・追加
- コンパクト化・リファクタリング
- 出力フォーマットの変更
- フィルタリングルールの追加・変更

### 読み込み不要

以下の場合は参照ファイルの読み込み不要:
- typo修正、文言微調整
- 検索カテゴリの追加・削除のみ
- 行動原則の追加・修正のみ
- 既存セクション内の説明文の書き換え

## プロンプトサイズの確認

編集完了後、プロンプトサイズが8KB以下であることを確認すること。超過する場合はコンパクト化を検討する。

## スクリプトファースト原則の確認

プロンプト内に3行以上のコマンド列や日付計算・JSON加工が直書きされている場合、スクリプト化を検討すること。
詳細は `~/.shared-ai/references/script-first-guide.md` のセクション6「チェックリスト」を参照。

## ファイルパスの絶対パス指定

プロンプト内でファイルパスを指定する場合、**必ず `~/` プレフィックス付きの絶対パス**を使用すること。

- ✅ `~/Documents/works/scout_reports/tech_trends/daily/tmp/feeds.md`
- ❌ `Documents/works/scout_reports/tech_trends/daily/tmp/feeds.md`

**理由**: パイプラインがlaunchdから起動される場合、cwdが `/` になるため相対パスでは
`/Documents/works/...` として解決され、macOSのSIPにより `Read-only file system` エラーが発生する。
