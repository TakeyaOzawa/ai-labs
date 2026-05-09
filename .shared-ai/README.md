# ~/.shared-ai/ — AI共通ナレッジベース

全体のセットアップ手順・アーキテクチャは [~/README.md](../README.md) を参照。

## ディレクトリ構造

```
~/.shared-ai/
├── README.md              # 本ファイル
├── rules/                 # 行動ルール（全ツール共通）
├── lookups/               # データ参照ガイド（ユーザーID逆引き等）
├── prompts/               # エージェントプロンプト本体
├── references/            # 参照データ（ソースリスト、ガイド等）
├── templates/             # フォーマットガイド（spec作成テンプレート等）
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

| steering ラッパー | 本体（shared-ai） | 配置先 |
|---|---|---|
| `dev-environment-rules.md` | `dev-environment.md` | `rules/` |
| `gws-integration-rules.md` | `gws-integration.md` | `rules/` |
| `python-script-coding-standards.md` | `python-coding-standards.md` | `rules/` |
| `shell-script-coding-standards.md` | `shell-coding-standards.md` | `rules/` |
| `pr-creation-base.md` | `pr-creation.md` | `rules/` |
| `slack-user-lookup-guide.md` | `slack-user-lookup.md` | `lookups/` |
| `notion-user-lookup-guide.md` | `notion-user-lookup.md` | `lookups/` |
| `slack-channel-mapping.md` | `slack-channel-mapping.md` | `lookups/` |
| `knowledge-management-base.md` | `knowledge-management-guide.md` | `references/` |
| `task-management-guide.md` | `task-management-guide.md` | `references/` |
| `implementation-plan-guide.md` | `implementation-plan-guide.md` | `references/` |
| `agent-workflow-guide.md` | `agent-workflow-guide.md` | `references/` |
| `steering-file-reference-rules.md` | `steering-reference-guide.md` | `references/` |
| `requirements-format-guide.md` | `spec-requirements-guide.md` + `spec-requirements.md` | `references/` + `templates/` |
| `design-format-guide.md` | `spec-design-guide.md` + `spec-design.md` | `references/` + `templates/` |
| `tasks-format-guide.md` | `spec-tasks-guide.md` + `spec-tasks.md` | `references/` + `templates/` |

## 更新手順

### ルール・プロンプトの変更

このディレクトリ内のファイルを直接編集する。変更は全ツールに自動反映される。

### 新しいルールを追加する場合

1. `rules/` に新しいmdファイルを作成
2. 各ツールの参照設定を追加:
   - Kiro: `~/.kiro/steering/` にWrapper_Fileを作成
   - Codex: `ln -s ~/.shared-ai/rules/xxx.md ~/.codex/rules/xxx.md`
   - Claude Code: `~/.claude/CLAUDE.md` に参照パスを追記
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
