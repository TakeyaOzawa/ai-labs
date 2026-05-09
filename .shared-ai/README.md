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

| ディレクトリ | 内容 | 例 |
|---|---|---|
| `rules/` | 全ツール共通の行動ルール・コーディング規約 | dev-environment.md, python-coding-standards.md |
| `lookups/` | ユーザーID逆引き、チャンネルマッピング等のデータ参照手順 | slack-user-lookup.md, notion-user-lookup.md |
| `prompts/` | カスタムエージェントのプロンプト本体 | agent-creator.md, slack-trend-scout.md |
| `references/` | エージェント作成ガイド、spec記述ガイド等の参照データ | agent-creation-guide.md, spec-requirements-guide.md |
| `templates/` | spec作成テンプレート、README テンプレート | spec-requirements.md, spec-design.md, readme.md |
| `skills/` | GWS CLI等の共通スキル定義（SKILL.md） | gws-gmail/, gws-drive/, gws-calendar/ |

## ファイルリネームマッピング

Kiro steering固有のサフィックス（`-rules`, `-guide`, `-base`）を除去してシンプルな名前に統一。

| 元ファイル名（Kiro steering） | 移行後ファイル名（shared-ai） | 配置先 |
|---|---|---|
| `dev-environment-rules.md` | `dev-environment.md` | `rules/` |
| `gws-integration-rules.md` | `gws-integration.md` | `rules/` |
| `python-script-coding-standards.md` | `python-coding-standards.md` | `rules/` |
| `shell-script-coding-standards.md` | `shell-coding-standards.md` | `rules/` |
| `pr-creation-base.md` | `pr-creation.md` | `rules/` |
| `slack-user-lookup-guide.md` | `slack-user-lookup.md` | `lookups/` |
| `notion-user-lookup-guide.md` | `notion-user-lookup.md` | `lookups/` |
| `slack-channel-mapping.md` | `slack-channel-mapping.md` | `lookups/` |
| `requirements-format-guide.md` | `spec-requirements.md` + `spec-requirements-guide.md` | `templates/` + `references/` |
| `design-format-guide.md` | `spec-design.md` + `spec-design-guide.md` | `templates/` + `references/` |
| `tasks-format-guide.md` | `spec-tasks.md` + `spec-tasks-guide.md` | `templates/` + `references/` |

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
