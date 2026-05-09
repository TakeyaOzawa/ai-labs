---
inclusion: fileMatch
fileMatchPattern: ".kiro/**/*.{md,json,hook}"
---

# Kiro アーキテクチャルール

`.kiro/` 配下のファイルを編集中です。以下の設計原則を遵守してください。

## 原則

### 1. 軽量ラッパー

`.kiro/steering/`, `.kiro/hooks/`, `.kiro/agents/` は薄いラッパーに徹する。
- **steering**: front-matter + readFile指示のみ（3〜5行）。本体は `~/.shared-ai/` に配置
- **hooks**: イベント判定 + readFile指示のみ。詳細手順は `~/.shared-ai/prompts/` に委譲
- **agents JSON**: メタデータ + `prompt: "file://..."` のみ。プロンプト本体は `~/.shared-ai/prompts/` に配置

### 2. agents-prompts 1:1対応

`.kiro/agents/{name}.json` と `.shared-ai/prompts/{name}.md` は必ず1:1で対応する。
- agent JSONを作成したら、対応するpromptファイルも作成すること
- promptファイルを削除する場合は、対応するagent JSONも削除すること

### 3. ガイド分離

プロンプト内の再利用可能なルール・手順は `~/.shared-ai/references/` に切り出す。
- 複数エージェントやhookから参照される判定基準・設計パターン → `references/{topic}-guide.md`
- プロンプトには「readFile: references/xxx.md」の指示のみ残す
- エージェント固有のワークフロー（Step 1→2→3の流れ）はプロンプトに残してよい

### 4. steering優先・hook最小化

kiro-cliではhookが発火しないため、**steeringで実現できることはsteeringで実装する**。

#### steeringを使うべきケース（優先）

- ファイル編集時のルール注入・フォーマット確認
- コーディング規約の適用
- 参照ファイルの読み込み指示
- 判断基準・チェック項目の提示

#### hookを使うべきケース（限定的）

以下の**全て**に該当する場合のみhookを作成する:
1. **IDE内でのみ実行される**ことが前提（kiro-cliでは別途シェルスクリプトで対応）
2. **イベント駆動が必須**（ファイル書き込み検知、エージェント完了検知等）
3. **自動実行が必要**（人間の介入なしに処理を開始したい）
4. steeringの `fileMatch` では実現できない（write操作の検知、agentStop等）

#### hookを作成した場合の義務

- kiro-cli方式でも同等の機能が動作するよう、対応するシェルスクリプトのステップを追加すること
- `agent-pipeline-guide.md` の「制約と注意事項」に kiro-cli での代替手段を記載すること

## チェック項目

- [ ] steering に本体（10行超のルール・手順）を直接書いていないか
- [ ] agent JSON に対応する `prompts/{name}.md` が存在するか
- [ ] prompt 内に他エージェントでも使える汎用ルールが埋め込まれていないか
- [ ] 新規hookを作成する場合、kiro-cli方式での代替手段が用意されているか
