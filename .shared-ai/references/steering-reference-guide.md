# Steering ファイル参照ガイド

グローバルsteeringとワークスペースsteeringの共存ルール。ファイル参照パスの解決方法と注意事項。

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

- `~/.kiro/steering/pr-creation.md` + `.kiro/steering/pr-creation-guide.md`
- `~/.kiro/steering/knowledge-mgmt.md` + `.kiro/steering/knowledge-management-rules.md`

### 配置の使い分け

| 配置先              | 用途                                                       | 例                                                                 |
| ------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| `~/.kiro/steering/` | プロジェクト非依存の汎用ルール                             | SDDフォーマットガイド、ナレッジ管理基本ルール、PR作成基本ガイド    |
| `.kiro/steering/`   | プロジェクト固有のルール、グローバルルールのオーバーライド | プロジェクト用語集、固有のディレクトリ構造、固有のブランチ命名規則 |

## inclusion type の選択基準

steeringファイルの `inclusion` front-matter は、コンテキスト消費と適用精度のトレードオフで選択する。

### 判定フロー

1. **ファイル操作に依存しない＋常時必要**（Slack/Notion/GWS連携、環境情報など）→ `always`
2. **特定ファイル編集時のみ必要**（コーディング規約、フォーマットルールなど）→ `fileMatch`
3. **リクエスト内容に応じて自動判断させたい**（ドメイン知識、ワークフローガイドなど）→ `auto`
4. **ユーザーが明示的に指定するワークフロー**（低頻度・大規模な手順）→ `manual`

### 比較表

| inclusion | コンテキスト消費 | 適用の確実性 | 必須フィールド | 適するケース |
|-----------|-----------------|-------------|---------------|-------------|
| `always`（デフォルト） | 常時消費 | 確実 | なし | ファイルパターンで条件を絞れないルール |
| `fileMatch` | 条件一致時のみ | Kiroの判定に依存（不発の場合あり） | `fileMatchPattern` | 特定ファイル種別に紐づくルール |
| `auto` | リクエスト一致時のみ | Kiroのdescriptionマッチに依存 | `name`, `description` | ドメイン知識、複雑なワークフロー |
| `manual` | ユーザー指定時のみ | ユーザー依存 | なし | 低頻度・大規模なワークフロー |

### front-matter の書式

```yaml
# always（デフォルト。省略可）
---
inclusion: always
---

# fileMatch（単一パターン）
---
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# fileMatch（複数パターン — 配列形式で指定）
---
inclusion: fileMatch
fileMatchPattern: ["**/*.ts", "**/*.tsx", "**/tsconfig.*.json"]
---

# auto（name と description が必須）
---
inclusion: auto
name: api-design
description: REST API設計パターン。APIエンドポイントの作成・変更時に使用。
---

# manual
---
inclusion: manual
---
```

### fileMatch の不発対策

`fileMatch` はKiroの内部判定に依存するため、期待通りにインクルードされない場合がある。対策として `~/.kiro/steering/filematch-dispatcher.md`（`inclusion: always`、数行の薄いルール）をフォールバックディスパッチャーとして配置し、エージェントが実行時に該当steeringをreadFileで読み込む構成を推奨する。

### 設計原則

- `always` 側は可能な限り薄くする（「readFileで○○を読め」の1行程度）
- 本体のルール・ガイドは `~/.shared-ai/references/` や `~/.shared-ai/rules/` に配置し、必要時のみ読み込ませる
- `fileMatch` を新規追加した場合は `filematch-dispatcher.md` のテーブルにも追記する
- `fileMatchPattern` で複数パターンを指定する場合は配列形式 `["pattern1", "pattern2"]` を使用する（カンマ区切り文字列は非推奨）
- `auto` を使用する場合は `name` と `description` を必ず指定する

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
- グローバルsteeringは `inclusion: always`（デフォルト）であれば自動読み込みされるため、agentのresourcesに明示的に追加する必要はない
- agentのresourcesにはワークスペース固有のファイルのみを指定する
