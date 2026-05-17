# shared-ai rules/ を critical/quality/ に再分類

## 変更種別

refactor

## 概要

- `rules/always/` を廃止し、ディスパッチャーを `rules/` 直下に配置
- `rules/contextual/` を `rules/critical/` と `rules/quality/` に分割
- references/ の定義を「詳細情報・具体例・未標準化のドラフト」に更新

## 問題・背景

- 現在の `rules/contextual/` に「違反時に即座に問題が起きるルール」と「品質維持のためのルール」が混在
- `always/` というディレクトリ名が「いつ読むか」を表しており、「何のためのルールか」が不明確
- references/ の位置づけが曖昧（標準化済みのガイドと未標準化のドラフトが混在）

## 新しいディレクトリ構造

```
rules/
├── filematch-dispatcher.md    # 直下にディスパッチャー
├── command-dispatcher.md
├── critical/                  # 違反時に即座に問題が起きる
│   ├── dev-environment.md
│   ├── test-db-guard.md
│   ├── env-sync.md
│   ├── spec-frontmatter.md
│   └── domain-frontmatter.md
└── quality/                   # 品質を一定に保つ
    ├── python-coding-standards.md
    ├── shell-coding-standards.md
    ├── readme-guide.md
    ├── pr-creation.md
    └── gws-integration.md
```

## 分類基準

| critical/ | quality/ |
|---|---|
| 違反時にSSL通信エラー、DB破壊、データ不整合が発生 | 違反時に品質が下がるが動作はする |
| サイズ: 〜2KB | サイズ: 2〜5KB |
| 例: dev-environment, test-db-guard, env-sync | 例: python-coding-standards, readme-guide |

## references/ の再定義

| 観点 | rules/ (critical + quality) | references/ |
|---|---|---|
| 内容 | 標準化されたルール（従うべき） | 詳細情報・具体例・未標準化のドラフト |
| 読み方 | 条件に該当したら必ず従う | 必要に応じて参照する |
| ライフサイクル | 安定（変更頻度低） | 発展途上（標準化されたらrules/に昇格） |

## 修正対象

### ディレクトリ操作
- `rules/always/filematch-dispatcher.md` → `rules/filematch-dispatcher.md` に移動
- `rules/always/command-dispatcher.md` → `rules/command-dispatcher.md` に移動
- `rules/always/` ディレクトリ削除
- `rules/contextual/` → `rules/critical/` と `rules/quality/` に分割

### パス更新が必要なファイル
- `~/scripts/resolve-shared-ai-rules.py` — RULESリストの全パス
- `~/scripts/setup-symlinks.py` — symlink定義のターゲットパス
- `~/.kiro/steering/filematch-dispatcher.md` — readFile参照先
- `~/.kiro/steering/command-dispatcher.md` — readFile参照先
- `~/.kiro/steering/py-standards.md` — readFile参照先
- `~/.kiro/steering/sh-standards.md` — readFile参照先
- `~/.kiro/steering/pr-creation.md` — readFile参照先
- `~/.kiro/steering/env-sync.md` — readFile参照先
- `~/.kiro/steering/test-db-guard.md` — readFile参照先
- `~/.kiro/steering/domain-frontmatter.md` — readFile参照先
- `~/.kiro/steering/spec-frontmatter.md` — readFile参照先
- `~/.shared-ai/rules/filematch-dispatcher.md` — スクリプトパス（変更なし）
- `~/.shared-ai/rules/command-dispatcher.md` — テーブル内パス
- `~/.shared-ai/README.md` — ディレクトリ構造・対応表
- `~/.shared-ai/references/shared-ai-directory-guide.md` — 配置判断基準・判断テーブル
- `~/.shared-ai/references/steering-reference-guide.md` — Wrapper_Fileテンプレートのパス
- `~/README.md` — ディレクトリ構成・運用手順
- `~/.claude/CLAUDE.md` — dispatcher参照パス
- `~/.gemini/GEMINI.md` — dispatcher参照パス
- `~/.codex/AGENTS.md` — dispatcher参照パス
- `~/.shared-ai/rules/contextual/dev-environment.md` — 内部参照パス

## タスク分解

### Task 1: ディレクトリ再構成

- ディスパッチャーを `rules/` 直下に移動
- `rules/contextual/` のファイルを `critical/` と `quality/` に振り分け
- `rules/always/` と `rules/contextual/` を削除

### Task 2: resolve-shared-ai-rules.py パス更新

- RULESリスト内の `rules/contextual/` → `rules/critical/` or `rules/quality/` に変更

### Task 3: setup-symlinks.py 更新

- symlink定義のターゲットパスを `rules/always/` → `rules/` 直下に変更
- 存在確認パスを更新

### Task 4: Kiro steering パス更新

- 全steeringファイルのreadFile参照先を新パスに更新

### Task 5: command-dispatcher.md テーブル内パス更新

- テーブル内の `rules/contextual/` → `rules/critical/` or `rules/quality/` に変更

### Task 6: ドキュメント更新

- `~/.shared-ai/README.md` — ディレクトリ構造・対応表
- `~/.shared-ai/references/shared-ai-directory-guide.md` — 配置判断基準
- `~/.shared-ai/references/steering-reference-guide.md` — Wrapper_Fileテンプレート
- `~/README.md` — ディレクトリ構成・運用手順
- `~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, `~/.codex/AGENTS.md` — dispatcher参照パス

## テスト計画

- [ ] `python3.12 ~/scripts/setup-symlinks.py --verify` が全て正常
- [ ] `python3.12 ~/scripts/resolve-shared-ai-rules.py "src/app.py"` が正しいパスを返す
- [ ] `python3.12 ~/scripts/resolve-shared-ai-rules.py "tests/Unit/UserTest.php"` が `critical/test-db-guard.md` を返す
- [ ] `python3.12 ~/scripts/resolve-shared-ai-rules.py "README.md"` が `quality/readme-guide.md` を返す
- [ ] 旧パス（`rules/always/`, `rules/contextual/`）への参照がプロジェクト内に残っていないこと
