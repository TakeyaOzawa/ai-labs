# ~/.shared-ai/ — AI共通ナレッジベース

全体のセットアップ手順・アーキテクチャは [~/README.md](../README.md) を参照。

## ディレクトリ構造

```
~/.shared-ai/
├── README.md              # 本ファイル
├── rules/                 # 行動制約（コーディング規約等）
├── lookups/               # マスタデータ（ID逆引き、チャンネル一覧等）
├── prompts/               # エージェントプロンプト（薄いラッパー）
├── references/            # 設計ガイド・手順書・パターン集（本体）
├── templates/             # 新規ファイル作成時の雛形
└── skills/                # 共通スキル（GWS CLI等）
```

### 各サブディレクトリの役割

| ディレクトリ | 性質 | 内容 | 例 |
|---|---|---|---|
| `rules/` | **行動制約** | 全セッションで常に守るべきルール・コーディング規約 | dev-environment.md, python-coding-standards.md |
| `lookups/` | **参照データ** | ID→名前の対応表、チャンネル一覧等のマスタデータ | slack-user-lookup.md, slack-channel-mapping.md |
| `prompts/` | **実行指示** | エージェント固有のワークフロー（薄いラッパー → references参照） | agent-creator.md, agent-output-reviewer.md |
| `references/` | **参照知識** | 設計ガイド、パターン集、手順書（本体） | agent-creation-guide.md, agent-prompt-guide.md |
| `templates/` | **雛形** | 新規ファイル作成時のスケルトン | spec-design.md, reference-guide.md |
| `skills/` | **ツール操作** | GWS CLI等の共通スキル定義（SKILL.md） | gws-gmail/, gws-drive/ |

### 配置判断基準

```
新しいファイルを追加する場合…
├─ 全セッションで常に守るべき制約？ → rules/
├─ ID/キー→値のマスタデータ？ → lookups/
├─ エージェント固有の実行フロー？ → prompts/（薄く、referencesを参照）
├─ 複数箇所から参照される設計知識・手順？ → references/
├─ 新規ファイル作成時の雛形？ → templates/
└─ 外部ツール操作のスキル？ → skills/
```

#### rules/ vs references/ の判断

| 観点 | rules/ | references/ |
|---|---|---|
| 適用タイミング | 常時（steering `inclusion: always`） | 必要時にreadFile |
| 内容の性質 | 「〜すること」「〜は禁止」 | 「〜の設計基準は以下の通り」 |
| サイズ | 短い（1〜2KB） | 長い（3〜8KB） |
| 違反時の影響 | 即座に問題が起きる | 品質が下がるが動作はする |

#### lookups/ vs references/ の判断

| 観点 | lookups/ | references/ |
|---|---|---|
| 内容 | 具体的なID/キー→値のマッピング | 設計方針・検索戦略・パターン |
| 更新方法 | 自動スクリプトで定期更新 | 手動で追加・修正 |
| 参照方法 | 実行時にデータとして「引く」 | 設計時に方針として「参照する」 |

#### prompts/ vs references/ の判断

| 観点 | prompts/ | references/ |
|---|---|---|
| 主語 | 「あなたは〜として動作してください」 | 「〜の設計基準は以下の通り」 |
| 読み方 | 上から順に従って実行する | 必要な箇所を参照する |
| 再利用性 | エージェント固有（1対1） | 複数箇所から参照される |

#### steering（.kiro/steering/）の設計

steeringは**薄いラッパー**として機能し、本体は `rules/` または `references/` に配置する:
- `inclusion` 設定（always / auto / fileMatch / manual）で「いつ注入するか」を制御
- 本体への `readFile` 指示のみを記載（3〜5行）
- ファイル名は `{トピック}-{文書種別}.md`（What を表す。When はfront-matterの責務）

## steering → shared-ai 対応表

`.kiro/steering/` の薄いラッパーが参照する `shared-ai/` 内の本体ファイル。

### 本体参照型（shared-ai/ にreadFile委譲）

| steering | 本体（shared-ai） | 配置先 |
|---|---|---|
| `dev-env.md` | `dev-environment.md` | `rules/` |
| `gws-rules.md` | `gws-integration.md` | `rules/` |
| `py-standards.md` | `python-coding-standards.md` | `rules/` |
| `sh-standards.md` | `shell-coding-standards.md` | `rules/` |
| `pr-creation.md` | `pr-creation.md` | `rules/` |
| `slack-lookup.md` | `slack-user-lookup.md` | `lookups/` |
| `notion-lookup.md` | `notion-user-lookup.md` | `lookups/` |
| `slack-channels.md` | `slack-channel-mapping.md` | `lookups/` |
| `knowledge-mgmt.md` | `knowledge-management-guide.md` | `references/` |
| `job-mgmt.md` | `job-management-guide.md` | `references/` |
| `pipeline-run-script.md` | `agent-pipeline-run-script-guide.md` | `references/` |
| `impl-plan.md` | `implementation-plan-guide.md` | `references/` |
| `steering-ref.md` | `steering-reference-guide.md` | `references/` |
| `prompt-editing.md` | `agent-prompt-guide.md` + `agent-creation-guide.md` | `references/` |
| `req-format.md` | `spec-requirements-guide.md` + `spec-requirements.md` | `references/` + `templates/` |
| `design-format.md` | `spec-design-guide.md` + `spec-design.md` | `references/` + `templates/` |
| `tasks-format.md` | `spec-tasks-guide.md` + `spec-tasks.md` | `references/` + `templates/` |

### 自己完結型（fileMatch、短いルール注入のみ）

| steering | 用途 | fileMatchPattern |
|---|---|---|
| `kiro-arch.md` | .kiro/配下の設計原則チェック | `.kiro/**/*.{md,json,hook}` |
| `ref-format.md` | referenceガイドのフォーマット確認 | `.shared-ai/references/*-guide.md` |
| `domain-frontmatter.md` | ドメインファイルのfront-matter確認 | `docs/domain/**/*.md` |
| `spec-frontmatter.md` | specファイルのfront-matter確認 | `.kiro/specs/**/*.md` |
| `spec-completion.md` | 全タスク完了時の提案 | `.kiro/specs/**/tasks.md` |
| `test-db-guard.md` | RefreshDatabase使用禁止 | `tests/**/*Test.php` |
| `poc-writer.md` | PoC完了→記事化提案 | `works/poc-something/**/SUMMARY.md` |

## 更新手順

### ルール・プロンプトの変更

このディレクトリ内のファイルを直接編集する。変更は全ツールに自動反映される。

### 新しいルールを追加する場合

1. `rules/` に新しいmdファイルを作成
2. 各ツールの参照設定を追加:
   - Kiro: `~/.kiro/steering/` にWrapper_Fileを作成
   - Codex: `ln -s ~/.shared-ai/rules/xxx.md ~/.codex/rules/xxx.md`
   - Claude Code: `~/.claude/CLAUDE.md` に参照パスを追記
   - Gemini: `~/.gemini/GEMINI.md` に参照パスを追記
3. `~/scripts/setup-shared-ai.py` にsymlink定義を追加（Codex rulesの場合）

### スキルを追加する場合

`skills/` に新しいスキルディレクトリを作成するだけ。symlinkにより全ツールから自動アクセス可能。

### Wrapper_File のフォーマット

Kiro steeringに配置するWrapper_Fileの形式:

```markdown
---
inclusion: always
description: {ルールの説明}
---

# {タイトル}

以下のファイルをreadFileで読み込み、その指示に従うこと:
- `~/.shared-ai/{category}/{filename}.md`
```
