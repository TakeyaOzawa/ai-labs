# github-repo-analysis-pipeline-redesign: パイプライン再設計

## 変更種別

refactor / feat

## 概要

`github-repo-analyst` の親エージェント方式（invokeSubAgent）を廃止し、`run-github-repo-analysis-pipeline.py` による独立プロセス逐次実行方式に移行する。各エージェントがコンテキスト汚染なく独立動作することを保証する。

## 問題・背景

- 現状: 親エージェント（github-repo-analyst）が `invokeSubAgent` でサブエージェントを呼び出す
- 問題1: サブエージェントの出力が親のコンテキストに蓄積され、後続エージェントのコンテキストを圧迫・汚染する
- 問題2: サブエージェントが親のコンテキストに依存する可能性があり、独立性が保証されない
- 問題3: IDE環境（invokeSubAgent可）とヘッドレス環境（不可）で実行方式が分岐し、保守が複雑

## 新パイプライン構成

```
run-github-repo-analysis-pipeline.py
│
├── Step 1: github-repo-analyst        → .tmp_{slug}_github.md
│   GitHub APIでメタデータ・履歴・計画を調査
│
├── Step 2: github-repo-analyst (参照先)→ .tmp_{slug}_refs.md
│   フォーク元・重要な関連リポジトリの追加調査
│
├── Step 3: web-searcher               → .tmp_{slug}_web.md
│   エコシステム・競合・導入事例のWeb調査
│
├── Step 4: code-analyst               → .tmp_{slug}_codebase.md
│   git clone → 実装パターン・アーキテクチャ分析
│
├── Step 5: markdown-reporter          → 最終レポート.md
│   一時ファイル統合 → 構造化レポート生成
│
├── Step 6: agent-output-reviewer      → レポート品質チェック
│   レポートの品質レビュー・修正
│
└── Step 7: slack-notifier             → Slack投稿
    レポートのSlack通知
```

## 各ステップの詳細

### Step 1: github-repo-analyst（GitHub API調査）

- **入力**: リポジトリURL（owner/repo）
- **出力**: `.tmp_{slug}_github.md`
- **内容**: 現行 `github-repo-analyst-github.md` の内容をそのまま使用
- **kiro-cli実行**: `kiro-cli chat --agent github-repo-analyst --trust-all-tools --no-interactive "{prompt}"`
- **no-interactive対応**: プロンプトにリポジトリURL・基準日を全て含める（ユーザー確認なし）

### Step 2: github-repo-analyst（参照先リポジトリ調査）

- **入力**: Step 1の出力から抽出した重要な関連リポジトリ（フォーク元、主要依存先等、最大3つ）
- **出力**: `.tmp_{slug}_refs.md`
- **内容**: 関連リポジトリのREADME・構造・依存関係を概要レベルで調査
- **kiro-cli実行**: 同じ `github-repo-analyst` エージェントを別プロンプトで再実行
- **スキップ条件**: フォーク元がない＆重要な関連リポジトリがない場合はスキップ

### Step 3: web-searcher（Web調査）

- **入力**: リポジトリ名・説明・技術スタック（Step 1の出力から抽出）
- **出力**: `.tmp_{slug}_web.md`
- **内容**: 現行 `github-repo-analyst-web.md` の観点を `web-searcher` に移植
  - 公式ブログ・アナウンス
  - 競合比較・選定記事
  - 導入事例・本番運用レポート
  - エコシステム位置づけ
- **kiro-cli実行**: `kiro-cli chat --agent web-searcher --trust-all-tools --no-interactive "{prompt}"`
- **no-interactive対応**: テーマ・キーワードをプロンプトに直接埋め込む。出力先パスも指定。

### Step 4: code-analyst（コードベース分析）

- **入力**: リポジトリURL、デフォルトブランチ、主要言語
- **出力**: `.tmp_{slug}_codebase.md`
- **内容**: 現行 `github-repo-analyst-codebase.md` をリネーム・調整
- **kiro-cli実行**: `kiro-cli chat --agent code-analyst --trust-all-tools --no-interactive "{prompt}"`
- **no-interactive対応**: 全パラメータをプロンプトに含める

### Step 5: markdown-reporter（レポート統合）

- **入力**: 4つの一時ファイル（github, refs, web, codebase）
- **出力**: `Documents/works/scout_histories/github_repo_analysis/{date}_{slug}_analysis.md`
- **内容**: 一時ファイルを読み込み、最終レポート構成に統合・再構成
- **新規作成**: `markdown-reporter` エージェント（汎用レポート統合エージェント）
- **no-interactive対応**: 入力ファイルパスと出力先パスをプロンプトに含める

### Step 6: agent-output-reviewer（品質レビュー）

- **入力**: Step 5で生成されたレポートファイルパス
- **出力**: レポートの修正（問題があれば）
- **内容**: 既存の `agent-output-reviewer` をそのまま使用
- **kiro-cli実行**: `kiro-cli chat --agent agent-output-reviewer --trust-all-tools --no-interactive "{prompt}"`
- **no-interactive対応**: レビュー対象ファイルパスをプロンプトに含める。「レビュー: 1段階目」から開始する旨を明示。

### Step 7: slack-notifier（Slack通知）

- **入力**: 最終レポートファイルパス
- **出力**: Slack投稿
- **内容**: 既存の `slack-notifier` をそのまま使用
- **kiro-cli実行**: `kiro-cli chat --agent slack-notifier --trust-all-tools --no-interactive "file_path={path}"`
- **no-interactive対応**: 既に対応済み（file_pathパラメータのみで動作）

## 修正対象ファイル

### 新規作成

| ファイル | 内容 |
|---|---|
| `scripts/run-github-repo-analysis-pipeline.py` | パイプラインスクリプト |
| `scripts/extract-repo-analysis-data.py` | 機械可読データ抽出スクリプト（作成済み） |
| `.shared-ai/prompts/code-analyst.md` | コードベース分析エージェント（codebase.mdをリネーム・調整） |
| `.shared-ai/prompts/markdown-reporter.md` | 汎用レポート統合エージェント |
| `.shared-ai/interfaces/github-repo-analyst-output.md` | github-repo-analyst出力インターフェース定義（作成済み） |
| `.kiro/agents/code-analyst.json` | code-analyst のagent JSON |
| `.kiro/agents/markdown-reporter.json` | markdown-reporter のagent JSON |

### 更新

| ファイル | 変更内容 |
|---|---|
| `.shared-ai/prompts/github-repo-analyst-github.md` | → `github-repo-analyst.md` にリネーム。no-interactive対応（ユーザー確認を削除、プロンプトから全パラメータ受け取り） |
| `.kiro/agents/github-repo-analyst-github.json` | → `github-repo-analyst.json` に統合 |
| `.kiro/agents/agent-output-reviewer.json` | 変更なし（既にread/write権限あり） |
| `.kiro/hooks/github-repo-analysis.kiro.hook` | パイプラインスクリプト実行に変更 |
| `.shared-ai/prompts/web-searcher.md` | 出力先パス指定対応の追加（既存機能に影響なし） |

### 削除

| ファイル | 理由 |
|---|---|
| `.shared-ai/prompts/github-repo-analyst.md`（現行の親エージェント） | パイプラインスクリプトに置き換え |
| `.shared-ai/prompts/github-repo-analyst-web.md` | web-searcherに観点を移植して廃止 |
| `.shared-ai/prompts/github-repo-analyst-codebase.md` | code-analystにリネーム |
| `.kiro/agents/github-repo-analyst-web.json` | 廃止 |
| `.kiro/agents/github-repo-analyst-codebase.json` | code-analystにリネーム |

## no-interactive対応の要件

各エージェントが `kiro-cli chat --no-interactive` で正常動作するために:

1. **ユーザー確認の排除**: 「URLを指定してください」等の対話的プロンプトを削除
2. **全パラメータのプロンプト埋め込み**: 必要な情報は全てプロンプト文字列に含める
3. **出力先の明示**: 出力ファイルパスをプロンプトで指定
4. **エラー時の自己完結**: エラー時にユーザーに質問せず、エラーメッセージを出力して終了
5. **基準日の外部指定**: `python3.12 ~/scripts/get-jst-date.py` ではなく、プロンプトで基準日を渡す

## パイプラインスクリプトの設計

```python
# 使い方
# python3.12 scripts/run-github-repo-analysis-pipeline.py https://github.com/owner/repo
# python3.12 scripts/run-github-repo-analysis-pipeline.py https://github.com/owner/repo --skip-web --skip-review

# 特徴:
# - _pipeline_common.py は使用しない（入力がURLであり、日次/週次パイプラインとは構造が異なる）
# - ジョブファイル管理なし（オンデマンド実行）
# - 各ステップ間のデータ受け渡しは一時ファイル経由
# - Step 2（参照先）はStep 1の出力を解析して動的に決定
# - --skip-* オプションで個別ステップをスキップ可能
```

## エージェント命名の最終形

| エージェント名 | 役割 | 単独実行 | パイプライン実行 |
|---|---|:---:|:---:|
| `github-repo-analyst` | GitHub API調査 | ✅ | ✅ |
| `web-searcher` | Web深掘り調査 | ✅ | ✅ |
| `code-analyst` | コードベース分析 | ✅ | ✅ |
| `markdown-reporter` | レポート統合 | ✅ | ✅ |
| `agent-output-reviewer` | 品質レビュー | ✅ | ✅ |
| `slack-notifier` | Slack通知 | ✅ | ✅ |

全エージェントが単独でもパイプラインでも動作可能。

## タスク分解

### Task 1: code-analyst エージェント作成
- `github-repo-analyst-codebase.md` → `code-analyst.md` にリネーム・調整
- agent JSON作成
- no-interactive対応

### Task 2: markdown-reporter エージェント作成
- 新規プロンプト作成（一時ファイル読み込み → 統合レポート生成）
- agent JSON作成
- レポート構成テンプレートの定義

### Task 3: github-repo-analyst の再構成
- 現行の親エージェントプロンプトを廃止
- `github-repo-analyst-github.md` → `github-repo-analyst.md` にリネーム
- no-interactive対応（ユーザー確認削除、パラメータ受け取り）
- agent JSON更新

### Task 4: web-searcher の拡張
- 出力先パス指定機能の追加
- github-repo-analyst-web の観点（競合比較、導入事例等）をプロンプトテンプレートとして整理
- github-repo-analyst-web.md 廃止

### Task 5: パイプラインスクリプト作成
- `scripts/run-github-repo-analysis-pipeline.py` 新規作成
- Step間のデータ受け渡しロジック
- エラーハンドリング・リトライ
- --skip-* オプション

### Task 6: hook更新・旧ファイル削除
- `.kiro/hooks/github-repo-analysis.kiro.hook` 更新
- 旧ファイル削除（github-repo-analyst-web, github-repo-analyst-codebase等）
- 参照漏れ確認

### Task 7: 動作確認
- 実際のリポジトリでパイプライン実行
- 各ステップの出力確認
- エラーケースの確認（クローン失敗、API制限等）

## 影響範囲

- 既存の日次/週次パイプラインには影響なし
- `web-searcher` は出力先指定機能の追加のみ（既存の単独実行に影響なし）
- `agent-output-reviewer` は変更なし（プロンプトの渡し方のみ工夫）
- `slack-notifier` は変更なし

## リスク・注意点

- Step 2（参照先リポジトリ）はStep 1の出力をパイプラインスクリプトが解析する必要がある → 一時ファイルのフォーマットを安定させる
- `web-searcher` に出力先パス指定を追加する際、既存の単独実行モードを壊さないこと
- `code-analyst` の `/tmp/repo-analyst/` クリーンアップが確実に行われること
- パイプライン全体の実行時間（7ステップ）が長くなる可能性 → 各ステップのタイムアウト設定を検討
