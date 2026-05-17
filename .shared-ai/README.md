# ~/.shared-ai/ — AI共通ナレッジベース

全体のセットアップ手順・アーキテクチャは [~/README.md](../README.md) を参照。

## ディレクトリ構造

```
~/.shared-ai/
├── README.md              # 本ファイル
├── rules/
│   ├── always/            # ディスパッチャー（常時読み込み）
│   └── contextual/        # 条件付きルール（dispatcher経由で読み込み）
├── lookups/               # マスタデータ（ID逆引き、チャンネル一覧等）
├── prompts/               # エージェントプロンプト（薄いラッパー）
├── references/            # 設計ガイド・手順書・パターン集（本体）
├── interfaces/            # エージェントの出力フォーマット・入力リソース定義
├── templates/             # 新規ファイル作成時の雛形
└── skills/                # 共通スキル（GWS CLI等）
```

### 各サブディレクトリの役割

| ディレクトリ | 性質 | 内容 | 例 |
|---|---|---|---|
| `rules/always/` | **ディスパッチャー** | 常時読み込み。条件に応じてcontextual/やlookups/への参照を指示 | filematch-dispatcher.md, command-dispatcher.md |
| `rules/contextual/` | **行動制約** | 該当時に必ず守るべきルール・コーディング規約（禁止・命令） | dev-environment.md, python-coding-standards.md |
| `lookups/` | **参照データ** | ID→名前の対応表、チャンネル一覧等のマスタデータ | slack-user-lookup.md, slack-channel-mapping.md |
| `prompts/` | **実行指示** | エージェント固有のワークフロー（薄いラッパー → references参照） | agent-creator.md, agent-output-reviewer.md |
| `references/` | **参照知識** | 設計ガイド、パターン集、手順書（本体） | agent-creation-guide.md, agent-prompt-guide.md |
| `interfaces/` | **入出力仕様** | エージェントの出力フォーマット・入力リソース定義 | notion-trend-scout-output.md, tech-poc-planner-output.md |
| `templates/` | **雛形** | 新規ファイル作成時のスケルトン | spec-design.md, reference-guide.md |
| `skills/` | **ツール操作** | GWS CLI等の共通スキル定義（SKILL.md） | gws-gmail/, gws-drive/ |

### 配置判断基準

`~/.shared-ai/` 配下にファイルを追加する際の判断基準は `shared-ai-directory-guide.md` を参照。

## ディスパッチャー方式

ディスパッチャーの仕組み（概要、各ツール参照方式、ルール追加手順）は `shared-ai-directory-guide.md` を参照。

## steering（.kiro/steering/）の設計

steeringは**薄いラッパー**として機能し、本体は `rules/contextual/` または `references/` に配置する。
設計原則・inclusion type選択基準・Wrapper_Fileテンプレートの詳細は `steering-reference-guide.md` を参照。

### steering → shared-ai 対応表

`.kiro/steering/` の薄いラッパーが参照する `shared-ai/` 内の本体ファイル。

#### ディスパッチャー型（always）

| steering | 本体（shared-ai） |
|---|---|
| `filematch-dispatcher.md` | `rules/always/filematch-dispatcher.md` |
| `command-dispatcher.md` | `rules/always/command-dispatcher.md` |

#### ルール参照型（contextual）

| steering | 本体（shared-ai） | 配置先 |
|---|---|---|
| `py-standards.md` | `python-coding-standards.md` | `rules/contextual/` |
| `sh-standards.md` | `shell-coding-standards.md` | `rules/contextual/` |
| `pr-creation.md` | `pr-creation.md` | `rules/contextual/` |
| `env-sync.md` | `env-sync.md` | `rules/contextual/` |
| `domain-frontmatter.md` | `domain-frontmatter.md` | `rules/contextual/` |
| `test-db-guard.md` | `test-db-guard.md` | `rules/contextual/` |
| `spec-frontmatter.md` | `spec-frontmatter.md` | `rules/contextual/` |

#### ガイド参照型（references）

| steering | 本体（shared-ai） | 配置先 |
|---|---|---|
| `knowledge-mgmt.md` | `knowledge-management-guide.md` | `references/` |
| `job-mgmt.md` | `job-management-guide.md` | `references/` |
| `pipeline-run-script.md` | `agent-pipeline-run-script-guide.md` | `references/` |
| `impl-plan.md` | `implementation-plan-guide.md` | `references/` |
| `steering-ref.md` | `steering-reference-guide.md` | `references/` |
| `script-first-rule.md` | `script-first-guide.md` | `references/` |
| `prompt-editing.md` | `prompt-editing-guide.md` | `references/` |
| `ref-format.md` | `reference-format-guide.md` | `references/` |
| `poc-writer.md` | `poc-writer-guide.md` | `references/` |
| `req-format.md` | `spec-requirements-guide.md` + `spec-requirements.md` | `references/` + `templates/` |
| `design-format.md` | `spec-design-guide.md` + `spec-design.md` | `references/` + `templates/` |
| `tasks-format.md` | `spec-tasks-guide.md` + `spec-tasks.md` | `references/` + `templates/` |

#### 自己完結型（Kiro固有ロジックのみ）

| steering | 用途 | fileMatchPattern |
|---|---|---|
| `kiro-arch.md` | .kiro/配下の設計原則チェック | `.kiro/**/*.{md,json,hook}` |
| `spec-completion.md` | 全タスク完了時の提案 | `.kiro/specs/**/tasks.md` |

## 更新手順

### ルール・プロンプトの変更

このディレクトリ内のファイルを直接編集する。変更は全ツールに自動反映される。

### 新しいcontextualルールを追加する場合

`shared-ai-directory-guide.md` の「ルール追加時の手順」を参照。

### スキルを追加する場合

`skills/` に新しいスキルディレクトリを作成するだけ。symlinkにより全ツールから自動アクセス可能。

### Wrapper_File のフォーマット

Kiro steeringに配置するWrapper_Fileの形式。

詳細（inclusion type選択基準、各typeのテンプレート）は `steering-reference-guide.md` を参照。
