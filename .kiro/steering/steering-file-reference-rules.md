---
inclusion: auto
description: グローバルsteeringとワークスペースsteeringの共存ルール。ファイル参照パスの解決方法と注意事項を定義する
---

# Steering ファイル参照ルール

## グローバルとワークスペースの共存

Kiroは `~/.kiro/steering/` （グローバル）と `.kiro/steering/` （ワークスペース）の両方のsteeringを自動マージして読み込む。

### 優先順位

- 同名ファイルが両方に存在する場合、ワークスペース側が優先され、グローバル側は読み込まれない
- グローバル側のファイルはワークスペース側でオーバーライドできる

### 同名ファイルの回避

グローバルとワークスペースの両方を読み込ませたい場合は、ファイル名を変えて共存させる。

- グローバル: `{topic}-base.md`（汎用ルール）
- ワークスペース: `{topic}-guide.md` または `{topic}-rules.md`（プロジェクト固有の追加定義）

例:

- `~/.kiro/steering/pr-creation-base.md` + `.kiro/steering/pr-creation-guide.md`
- `~/.kiro/steering/knowledge-management-base.md` + `.kiro/steering/knowledge-management-rules.md`

### 配置の使い分け

| 配置先              | 用途                                                       | 例                                                                 |
| ------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| `~/.kiro/steering/` | プロジェクト非依存の汎用ルール                             | SDDフォーマットガイド、ナレッジ管理基本ルール、PR作成基本ガイド    |
| `.kiro/steering/`   | プロジェクト固有のルール、グローバルルールのオーバーライド | プロジェクト用語集、固有のディレクトリ構造、固有のブランチ命名規則 |

## `#[[file:]]` 参照パスの注意事項

### グローバルsteeringでの参照

グローバルsteeringのテンプレート内で `#[[file:.kiro/steering/...]]` を使用する場合、そのパスはワークスペースの `.kiro/steering/` を指す。

つまり、グローバルsteeringのテンプレートが `#[[file:.kiro/steering/glossary-core.md]]` を参照している場合:

- 各ワークスペースに `.kiro/steering/glossary-core.md` が存在する必要がある
- グローバル側の `~/.kiro/steering/glossary-core.md` は参照されない

### 推奨パターン

1. テンプレート内のファイル参照（`#[[file:]]`）はワークスペース側のファイルを指すようにする
2. 各プロジェクトで必要な用語集やドメイン固有ファイルはワークスペースの `.kiro/steering/` に配置する
3. グローバルsteeringはテンプレート構造やフォーマットルールなど、ファイル参照を含まない汎用ルールに使用する

### agentのresources参照

agentのJSONファイル（`.kiro/agents/*.json`）の `resources` フィールドで `file://` を使用する場合:

- `file://.kiro/steering/...` はワークスペースの `.kiro/steering/` を参照する
- グローバルsteeringは `inclusion: auto` であれば自動読み込みされるため、agentのresourcesに明示的に追加する必要はない
- agentのresourcesにはワークスペース固有のファイルのみを指定する
