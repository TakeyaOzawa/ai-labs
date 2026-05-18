# readme-documentation-audit: README/ドキュメント整合性修正

## 変更種別

docs

## 概要

- `~/README.md`、`~/.shared-ai/README.md`、`scripts/README.md` の記載内容と実態の乖離を修正する
- 今後の継続的な整合性チェックのための汎用スクリプトを作成する

## 問題・背景

網羅的なドキュメント監査により、以下の問題が検出された:
- リンク切れ（ファイル移動後の参照未更新）
- 実装との乖離（symlinkテーブル、依存関係図の不足）
- 対応表の記載漏れ（新規steering追加時の反映忘れ）
- 設計原則違反（agents-prompts 1:1対応の例外）
- スクリプト一覧の未更新
- 不要ファイルの残存

## 修正対象

- `~/README.md`
- `~/.shared-ai/README.md`
- `scripts/README.md`
- `~/.shared-ai/references/shared-ai-directory-guide.md`（命名規則の例外追記）
- `scripts/audit-documentation.py`（新規作成）

## タスク分解

### Task 1: `~/README.md` リンク切れ修正

- **対象ファイル:** `~/README.md`
- **変更内容:**
  - §9 関連ドキュメントの `issues/shared-ai-knowledge-base.md` → `issues/completed/shared-ai-knowledge-base.md` に修正

### Task 2: `~/README.md` symlinkテーブル追記

- **対象ファイル:** `~/README.md`
- **変更内容:**
  - §3.2 symlinkテーブルに `.git/hooks/pre-commit → scripts/git-hooks/pre-commit` を追加

### Task 3: `~/README.md` 依存関係図の補完

- **対象ファイル:** `~/README.md`
- **変更内容:**
  - §5.2 依存関係図に `.kiro/steering/*.md ─── readFile ───→ .shared-ai/references/` を追加
  - `.git/hooks/pre-commit ─── symlink ───→ scripts/git-hooks/pre-commit` を追加

### Task 4: `~/.shared-ai/README.md` steering対応表に `shared-ai-verify.md` 追加

- **対象ファイル:** `~/.shared-ai/README.md`
- **変更内容:**
  - 「自己完結型」セクションに `shared-ai-verify.md` を追加

### Task 5: `scripts/README.md` スクリプト一覧の更新

- **対象ファイル:** `scripts/README.md`
- **変更内容:**
  - 主要スクリプトテーブルに未記載のスクリプトを追加（パイプライン系、ユーティリティ系）
  - 内部モジュール（`_pipeline_common.py`, `_version_check.py`, `logger.py`）の説明を追加

### Task 6: `slack-trend-scout-merge` の1:1対応違反の解消

- **対象ファイル:** `~/.kiro/agents/slack-trend-scout-merge.json`（新規作成）または `~/.shared-ai/prompts/slack-trend-scout-merge.md`（削除）
- **変更内容:**
  - パイプライン内部でのみ使用されるプロンプトであれば、agent JSONを作成して1:1対応を維持する
  - 使用されていない場合は削除する

### Task 7: `rss-source-updater.py` 重複の解消

- **対象ファイル:** `scripts/rss-source-updater.py`（旧版）、`scripts/rss_source_updater.py`（新版）
- **変更内容:**
  - 旧版 `rss-source-updater.py` が不要であれば削除する
  - 新版 `rss_source_updater.py` を命名規則に合わせてリネームするか、用途が異なるなら両方をREADMEに記載する

### Task 8: `interfaces/` 命名規則の例外を文書化

- **対象ファイル:** `~/.shared-ai/references/shared-ai-directory-guide.md`
- **変更内容:**
  - 命名規則セクションの `interfaces/` 行に例外パターンを追記:
    - `{topic}-schema.md` — 共通スキーマ定義
    - `{pipeline-name}-report-format.md` — パイプライン固有のレポートフォーマット

### Task 9: ドキュメント整合性チェックスクリプトの作成

- **対象ファイル:** `scripts/audit-documentation.py`（新規作成）
- **変更内容:**
  - README/ドキュメントの整合性を自動チェックするスクリプトを作成
  - チェック項目:
    1. README内のリンク先ファイルの実在確認
    2. steering対応表と実ファイルの双方向チェック
    3. agents-prompts 1:1対応チェック
    4. scripts/README.md のスクリプト一覧と実ファイルの差分検出
    5. interfaces/ の命名規則チェック
    6. symlink テーブルと setup-symlinks.py の定義の整合性チェック

## 影響範囲

- ドキュメントのみの変更（Task 1〜5, 8）は既存動作に影響なし
- Task 6, 7 はファイル追加/削除を伴うが、パイプライン動作への影響は要確認
- Task 9 は新規スクリプト追加のみ

## テスト計画

- [ ] `python3.12 ~/scripts/verify-shared-ai-structure.py` が全チェック PASS
- [ ] `python3.12 ~/scripts/audit-documentation.py` が全チェック PASS
- [ ] `~/README.md` 内の全リンクが有効であること
- [ ] `~/.shared-ai/README.md` の steering 対応表が実ファイルと一致すること
