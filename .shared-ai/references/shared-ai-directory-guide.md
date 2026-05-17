# shared-ai ディレクトリ配置ガイド

`~/.shared-ai/` 配下にファイルを追加・移動する際の配置判断基準と、ディスパッチャー方式の運用ルール。

## 配置判断フロー

```
新しいファイルを追加する場合…
├─ 該当時に必ず守るべき制約？（禁止・命令） → rules/contextual/
├─ ID/キー→値のマスタデータ？ → lookups/
├─ エージェント固有の実行フロー？ → prompts/（薄く、referencesを参照）
├─ 複数箇所から参照される設計知識・手順？ → references/
├─ エージェントの出力フォーマット・入力リソース定義？ → interfaces/
├─ 新規ファイル作成時の雛形？ → templates/
└─ 外部ツール操作のスキル？ → skills/
```

## rules/ のサブディレクトリ構造

| サブディレクトリ | 読み込みタイミング | 内容 |
|---|---|---|
| `always/` | 全セッションで常時 | ディスパッチャー（条件テーブル）のみ配置 |
| `contextual/` | dispatcher経由で条件付き | ルール本体（コーディング規約、禁止事項等） |

### always/ の設計原則

- **ディスパッチャーのみ配置**（ルール本体は置かない）
- ファイル数は最小限に抑える（コンテキスト消費を最小化）
- 各AIツールはalways/のみを常時読み込み、contextual/はdispatcher経由で条件付き参照

## ディスパッチャー方式

全AIツールは `rules/always/` の2つのディスパッチャーを常時参照する:

1. **filematch-dispatcher.md** — `~/scripts/resolve-shared-ai-rules.py` を実行し、ファイルパターンに基づくルール適用
2. **command-dispatcher.md** — コマンド/操作種別に基づくルール適用（lookups/含む）

### 各ツールの参照方式

| ツール | always/の参照方法 | contextual/の参照方法 |
|---|---|---|
| **Kiro** | steering `inclusion: always` → dispatcher readFile | steering `fileMatch` が優先、不発時はdispatcher経由 |
| **Claude Code** | CLAUDE.md にdispatcher参照を記載 | dispatcher経由で条件付き読み込み |
| **Gemini** | GEMINI.md にdispatcher参照を記載 | dispatcher経由で条件付き読み込み |
| **Codex** | `~/.codex/rules/` にalways/をsymlink | dispatcher経由で条件付き読み込み |

### ルール追加時の手順

新しいcontextualルールを追加する場合:

1. `rules/contextual/` に新しいmdファイルを作成
2. `~/scripts/resolve-shared-ai-rules.py` のRULESリストにパターンとターゲットを追記
3. `rules/always/command-dispatcher.md` のテーブルに追記（コマンド/操作種別に紐づく場合のみ）
4. （Kiroのみ・任意）`~/.kiro/steering/` にfileMatch Wrapper_Fileを作成

**CLAUDE.md / GEMINI.md / Codex の個別更新は不要**（dispatcherが自動的に新ルールを参照する）

## ディレクトリ間の判断基準

### contextual/ vs references/

| 観点 | rules/contextual/ | references/ |
|---|---|---|
| 内容の性質 | 「〜すること」「〜は禁止」 | 「〜の設計基準は以下の通り」 |
| サイズ | 短い（1〜2KB） | 長い（3〜8KB） |
| 違反時の影響 | 即座に問題が起きる | 品質が下がるが動作はする |
| 参照方法 | dispatcher経由で強制適用 | 必要時にreadFile |

### lookups/ vs references/

| 観点 | lookups/ | references/ |
|---|---|---|
| 内容 | 具体的なID/キー→値のマッピング | 設計方針・検索戦略・パターン |
| 更新方法 | 自動スクリプトで定期更新 | 手動で追加・修正 |
| 参照方法 | command-dispatcher経由で操作時に「引く」 | 設計時に方針として「参照する」 |

### prompts/ vs references/

| 観点 | prompts/ | references/ |
|---|---|---|
| 主語 | 「あなたは〜として動作してください」 | 「〜の設計基準は以下の通り」 |
| 読み方 | 上から順に従って実行する | 必要な箇所を参照する |
| 再利用性 | エージェント固有（1対1） | 複数箇所から参照される |

### interfaces/ vs references/

| 観点 | interfaces/ | references/ |
|---|---|---|
| 内容 | 「何を入力し、何を出力するか」の仕様 | 「なぜ・どうやって」の設計知識 |
| 読み方 | 仕様としてそのまま適用する | 方針として参照する |
| 変更頻度 | 出力項目追加・フォーマット変更時 | 設計方針変更時 |
| 再利用性 | 通常1エージェント固有 | 複数エージェントから参照 |
| 命名 | `{agent-name}-output.md`, `{agent-name}-resources.md` | `{topic}-guide.md`, `{topic}-sources.md` |

## 命名規則

| ディレクトリ | 命名パターン | 例 |
|---|---|---|
| `rules/contextual/` | `{対象}-{種別}.md`（ケバブケース） | `python-coding-standards.md`, `test-db-guard.md` |
| `references/` | `{トピック}-guide.md` / `{トピック}-sources.md` | `agent-prompt-guide.md`, `tech-trend-sources.md` |
| `prompts/` | `{エージェント名}.md` | `tech-blog-writer.md` |
| `interfaces/` | `{エージェント名}-output.md` / `{エージェント名}-resources.md` | `notion-trend-scout-output.md` |
| `templates/` | `{対象}.md` | `spec-design.md`, `reference-guide.md` |
| `lookups/` | `{サービス}-{種別}.md` | `slack-user-lookup.md`, `slack-channel-mapping.md` |
