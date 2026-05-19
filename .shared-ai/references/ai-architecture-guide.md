# AI環境 アーキテクチャガイド

`~/.shared-ai/` を中心としたAI開発環境の設計原則。全ツール（Kiro / Claude Code / Codex / Gemini / .agents）共通で遵守する。

## 設計原則

### 1. Single Source of Truth

`~/.shared-ai/` が全ツール共通ナレッジの唯一の実体。各ツール固有の設定ファイル（steering, CLAUDE.md, AGENTS.md等）は参照のみを持ち、実体を持たない。

- ルール変更は `~/.shared-ai/` 内のファイルを直接編集する
- 各ツール固有ファイルの編集は不要（symlink / readFile指示で自動反映）

### 2. 軽量ラッパー

各ツールの設定ファイルは薄いラッパーに徹する:

| ツール | ラッパー | 形式 |
|---|---|---|
| Kiro steering | `~/.kiro/steering/*.md` | front-matter + readFile指示（3〜5行） |
| Kiro agents | `~/.kiro/agents/*.json` | メタデータ + `prompt: "file://..."` |
| Claude Code | `~/.claude/CLAUDE.md` | 参照パス列挙 |
| Codex | `~/.codex/AGENTS.md` | 参照パス列挙 |
| Gemini | `~/.gemini/GEMINI.md` | 参照パス列挙 |

### 3. agents-prompts 1:1対応

`~/.kiro/agents/{name}.json` と `~/.shared-ai/prompts/{name}.md` は必ず1:1で対応する。

- agent JSONを作成したら、対応するpromptファイルも作成すること
- promptファイルを削除する場合は、対応するagent JSONも削除すること

### 4. ガイド分離

プロンプト内の再利用可能なルール・手順は `~/.shared-ai/references/` に切り出す:

- 複数エージェントから参照される判定基準・設計パターン → `references/{topic}-guide.md`
- プロンプトには「readFile: references/xxx.md」の指示のみ残す
- エージェント固有のワークフロー（Step 1→2→3の流れ）はプロンプトに残してよい

### 5. テンプレートとガイドの分離

`~/.shared-ai/templates/` と `~/.shared-ai/references/` は責務が異なる:

| ディレクトリ | 責務 | 内容 |
|---|---|---|
| `templates/` | コピーして使う骨格 | Markdownテンプレート、front-matter仕様 |
| `references/` | 読んで従うルール | 準拠規格、記述ルール、設計思想 |

### 6. symlink による共有

ファイルシステムレベルの共有にはsymlinkを使用する:

- ディレクトリsymlink: skills（全ツール共通）
- 個別ファイルsymlink: Codex rules
- clone後は `~/scripts/setup/setup-shared-ai.py` で復元

### 7. 新規ツール追加時の手順

新しいAIツールを導入する場合:

1. ツール固有の設定ファイル（CLAUDE.md相当）に shared-ai 参照パスを記載
2. skills が必要なら symlink を作成し、`setup-symlinks.py` に定義を追加
3. ルートREADME §4.2 の参照方式テーブルに追記

## チェック項目

新規ファイル作成・編集時に確認:

- [ ] shared-ai 内のファイルに実体があるか（ツール固有ファイルに実体を書いていないか）
- [ ] agent JSON に対応する `prompts/{name}.md` が存在するか
- [ ] prompt 内に他エージェントでも使える汎用ルールが埋め込まれていないか（→ references/ に切り出す）
- [ ] 新規ルール追加時に全ツールの参照設定が更新されているか
