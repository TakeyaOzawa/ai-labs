# shared-ai rules/ ディレクトリ再構成

## 変更種別

refactor

## 概要

- `~/.shared-ai/rules/` を `always/` と `contextual/` のサブディレクトリに分割する
- `always/` にはディスパッチャー（filematch-dispatcher.md, command-dispatcher.md）のみ配置
- 全ルール本体は `contextual/` に移動
- 各AIツール（Kiro steering, CLAUDE.md, GEMINI.md, Codex, .agents）の参照パスを更新
- symlink構成を再構築

## 問題・背景

- 現在 `rules/` 配下に「常時読み込むべきルール」と「条件付きで読み込むルール」が混在している
- 各AIツールの設定ファイル（CLAUDE.md等）にルールを個別列挙しており、ルール追加時に全ツールの設定を更新する必要がある
- ディスパッチャーパターンを導入することで、ルール追加時は dispatcher のテーブルに1行追加するだけで全ツールに反映される

## 修正対象

### 新規作成
- `~/.shared-ai/rules/always/filematch-dispatcher.md`
- `~/.shared-ai/rules/always/command-dispatcher.md`

### 移動（rules/ → rules/contextual/）
- `dev-environment.md`
- `gws-integration.md`
- `python-coding-standards.md`
- `shell-coding-standards.md`
- `pr-creation.md`
- `env-sync.md`
- `test-db-guard.md`
- `domain-frontmatter.md`
- `spec-frontmatter.md`

### 更新
- `~/.shared-ai/README.md` — ディレクトリ構造・配置基準・対応表
- `~/.claude/CLAUDE.md` — dispatcher参照方式に変更
- `~/.gemini/GEMINI.md` — dispatcher参照方式に変更
- `~/.codex/AGENTS.md` — dispatcher参照方式に変更
- `~/scripts/setup-symlinks.py` — 新しいsymlink定義
- `~/.kiro/steering/filematch-dispatcher.md` — shared-ai側dispatcherへの委譲
- `~/.kiro/steering/dev-env.md` — パス更新
- `~/.kiro/steering/gws-rules.md` — パス更新
- `~/.kiro/steering/py-standards.md` — パス更新
- `~/.kiro/steering/sh-standards.md` — パス更新
- `~/.kiro/steering/pr-creation.md` — パス更新
- `~/.kiro/steering/env-sync.md` — パス更新
- `~/.kiro/steering/test-db-guard.md` — パス更新
- `~/.kiro/steering/domain-frontmatter.md` — パス更新
- `~/.kiro/steering/spec-frontmatter.md` — パス更新

### 削除
- `~/.shared-ai/rules/dev-environment.md`（移動後の旧パス）
- `~/.shared-ai/rules/gws-integration.md`
- `~/.shared-ai/rules/python-coding-standards.md`
- `~/.shared-ai/rules/shell-coding-standards.md`
- `~/.shared-ai/rules/pr-creation.md`
- `~/.shared-ai/rules/env-sync.md`
- `~/.shared-ai/rules/test-db-guard.md`
- `~/.shared-ai/rules/domain-frontmatter.md`
- `~/.shared-ai/rules/spec-frontmatter.md`
- `~/.codex/rules/` 配下の既存symlink（再構築）

## タスク分解

### Task 1: rules/always/ ディスパッチャー作成

- **対象ファイル:** `~/.shared-ai/rules/always/filematch-dispatcher.md`, `~/.shared-ai/rules/always/command-dispatcher.md`
- **変更内容:** ファイルパターン別・コマンド別のルール適用テーブルを作成。フォールバック注記を含む

### Task 2: rules/contextual/ へファイル移動

- **対象ファイル:** 既存の `rules/` 直下9ファイル
- **変更内容:** `rules/contextual/` サブディレクトリに移動

### Task 3: Kiro steering パス更新

- **対象ファイル:** `~/.kiro/steering/` 配下の該当ファイル
- **変更内容:** readFile参照先を `rules/contextual/` パスに更新。filematch-dispatcherはshared-ai側への委譲に変更

### Task 4: 各AIツール設定ファイル更新

- **対象ファイル:** `~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, `~/.codex/AGENTS.md`
- **変更内容:** 個別ルール列挙をdispatcher参照方式に変更

### Task 5: setup-symlinks.py 再構築

- **対象ファイル:** `~/scripts/setup-symlinks.py`
- **変更内容:** FILE_SYMLINKSを`always/`配下のディスパッチャーへのsymlinkに変更。旧symlink削除ロジック追加

### Task 6: README.md 更新

- **対象ファイル:** `~/.shared-ai/README.md`
- **変更内容:** ディレクトリ構造、配置判断基準、対応表を新構造に合わせて更新

## 影響範囲

- 全AIツール（Kiro, Claude Code, Gemini, Codex, .agents）のルール参照パス
- `setup-symlinks.py` による自動構築
- 既存のCodex symlink

## テスト計画

- [x] `python3.12 ~/scripts/setup-symlinks.py --verify` が全て正常
- [ ] Kiro steeringのfileMatchが正しく発火し、contextual/のルールが読み込まれる
- [ ] filematch-dispatcherのフォールバックが機能する（resolve-shared-ai-rules.py経由）
- [ ] command-dispatcherからlookups/が正しく参照される
- [x] resolve-shared-ai-rules.py の全パターンマッチが正常動作

## 追加対応: filematch-dispatcher のスクリプト化

### Task 7: resolve-shared-ai-rules.py 作成

- **対象ファイル:** `~/scripts/resolve-shared-ai-rules.py`
- **変更内容:** ファイルパスを引数に受け取り、該当するルール/リファレンスのパスを改行区切りで出力するユーティリティスクリプト
- **出力形式:** 改行区切り（該当なしなら空出力、エラー時はstderrにJSON）

### Task 8: filematch-dispatcher.md をスクリプト呼び出し方式に変更

- **対象ファイル:** `~/.shared-ai/rules/always/filematch-dispatcher.md`, `~/.kiro/steering/filematch-dispatcher.md`
- **変更内容:** テーブル方式からスクリプト実行指示に変更。コンテキスト消費を約70%削減
