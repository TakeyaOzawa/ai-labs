# shared-ai-knowledge-base: AI共通ナレッジベースの構築

## 変更種別

refactor

## 概要

- Kiro / Claude Code / Codex CLI の3ツール間で重複管理されているmdファイル（ルール、プロンプト、参照データ、スキル）を `~/.shared-ai/` に集約し、各ツールからsymlinkまたはテキスト参照で利用する構造に移行する

## 問題・背景

- 現在、同一内容のファイルが `~/.kiro/steering/`, `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` に分散・重複している
- GWSスキルは `~/.kiro/skills/`, `~/.claude/skills/`, `~/.agents/skills/` に完全同一の内容が3重に配置されている
- ルール変更時に3箇所を手動で同期する必要があり、不整合が発生しやすい
- 新しいAIツールを導入する際に、毎回全ルールをコピーする必要がある

## 設計方針

### 参照方式の使い分け

| 対象 | 方式 | 理由 |
|---|---|---|
| skills | symlink | 各ツールが `~/.xxx/skills/` を直接読み込む機構を持つため |
| Codex rules | 個別ファイルsymlink | Codexが `~/.codex/rules/*.md` を自動読み込みするため |
| Kiro steering | テキスト参照指示 | `#[[file:]]` が親階層非対応。`inclusion: always` で指示を自動注入 |
| Claude Code CLAUDE.md | テキスト参照指示 | グローバルCLAUDE.mdに参照パスを列挙 |
| Codex AGENTS.md | テキスト参照指示 | グローバルAGENTS.mdに参照パスを列挙 |
| Kiro agent prompts | ラッパー方式 | `file://./prompts/xxx.md` の制約上、prompts/内に薄いラッパーを残す |

### ディレクトリ構造

```
~/.shared-ai/
├── README.md                   # 構造説明・各ツールからの参照方法
├── rules/                      # 行動ルール（全ツール共通）
│   ├── dev-environment.md
│   ├── gws-integration.md
│   ├── python-coding-standards.md
│   ├── shell-coding-standards.md
│   └── pr-creation.md
├── lookups/                    # データ参照ガイド
│   ├── slack-user-lookup.md
│   ├── notion-user-lookup.md
│   └── slack-channel-mapping.md
├── prompts/                    # エージェントプロンプト本体
│   ├── agent-creator.md
│   ├── slack-trend-scout.md
│   └── ...（全エージェント分）
├── references/                 # 参照データ
│   ├── agent-creation-guide.md
│   ├── agent-prompt-guide.md
│   ├── agent-pipeline-guide.md
│   ├── tech-trend-sources.md
│   └── ...
├── templates/                  # フォーマットガイド
│   ├── requirements-format.md
│   ├── design-format.md
│   └── tasks-format.md
└── skills/                     # 共通スキル（GWS等）
    ├── find-skills/
    ├── gws-gmail/
    ├── gws-drive/
    ├── gws-calendar/
    └── ...（全スキル）
```

## 修正対象

### 新規作成
- `~/.shared-ai/` ディレクトリ一式
- `~/.shared-ai/README.md`

### 移行（移動元 → 移動先）
- `~/.kiro/steering/{rules系}` → `~/.shared-ai/rules/`
- `~/.kiro/steering/{lookups系}` → `~/.shared-ai/lookups/`
- `~/.kiro/steering/{templates系}` → `~/.shared-ai/templates/`
- `~/.kiro/agents/prompts/*.md` → `~/.shared-ai/prompts/`
- `~/.kiro/agents/references/*.md` → `~/.shared-ai/references/`
- `~/.kiro/skills/*` → `~/.shared-ai/skills/`

### 変更（ラッパー化・symlink化）
- `~/.kiro/steering/` — 薄いラッパーに書き換え
- `~/.kiro/agents/prompts/` — readFile指示のラッパーに書き換え
- `~/.kiro/skills/` — symlink化
- `~/.claude/skills/` — symlink化
- `~/.agents/skills/` — symlink化
- `~/.claude/CLAUDE.md` — 参照パス追記
- `~/.codex/AGENTS.md` — 新規作成（参照パス記載）
- `~/.codex/rules/` — 個別ファイルsymlink作成

## 事前技術検証

### 検証1: Kiro skills ディレクトリのsymlink対応

**目的:** `~/.kiro/skills/` をsymlinkに置き換えてもKiroがスキルを正常に認識するか

**手順:**
```bash
# 1. バックアップ
cp -r ~/.kiro/skills ~/.kiro/skills.bak

# 2. テスト用ディレクトリ作成
mkdir -p /tmp/test-shared-skills
cp -r ~/.kiro/skills/* /tmp/test-shared-skills/

# 3. 元ディレクトリをリネームしてsymlink作成
mv ~/.kiro/skills ~/.kiro/skills.orig
ln -s /tmp/test-shared-skills ~/.kiro/skills

# 4. Kiroでスキル呼び出しテスト
# → Kiro IDEでGWSスキルを使うコマンドを実行（例: gws gmail list）
# → スキルが正常に読み込まれるか確認

# 5. 結果に関わらず復元
rm ~/.kiro/skills
mv ~/.kiro/skills.orig ~/.kiro/skills
rm -rf /tmp/test-shared-skills
```

**合格基準:** symlinkされたディレクトリからSKILL.mdが正常に読み込まれ、gws CLIが動作すること

**不合格時の代替案:** skillsはsymlink化せず、更新スクリプト（rsync）で同期する方式に切り替え

### 検証2: Claude Code skills ディレクトリのsymlink対応

**目的:** `~/.claude/skills/` をsymlinkに置き換えてもClaude Codeがスキルを正常に認識するか

**手順:**
```bash
# 1. バックアップ
cp -r ~/.claude/skills ~/.claude/skills.bak

# 2. テスト用ディレクトリ作成
mkdir -p /tmp/test-shared-skills-claude
cp -r ~/.claude/skills/* /tmp/test-shared-skills-claude/

# 3. 元ディレクトリをリネームしてsymlink作成
mv ~/.claude/skills ~/.claude/skills.orig
ln -s /tmp/test-shared-skills-claude ~/.claude/skills

# 4. Claude Codeでスキル呼び出しテスト
# → claude コマンドを起動し、GWSスキルを使う操作を実行
# → スキルが正常に読み込まれるか確認

# 5. 結果に関わらず復元
rm ~/.claude/skills
mv ~/.claude/skills.orig ~/.claude/skills
rm -rf /tmp/test-shared-skills-claude
```

**合格基準:** symlinkされたディレクトリからSKILL.mdが正常に読み込まれること

**不合格時の代替案:** 検証1と同じ（rsync同期方式）

### 検証3: .agents/skills ディレクトリのsymlink対応

**目的:** `~/.agents/skills/` をsymlinkに置き換えてもGoogle系エージェントがスキルを正常に認識するか

**手順:**
```bash
# 1. バックアップ
cp -r ~/.agents/skills ~/.agents/skills.bak

# 2. テスト用ディレクトリ作成
mkdir -p /tmp/test-shared-skills-agents
cp -r ~/.agents/skills/* /tmp/test-shared-skills-agents/

# 3. 元ディレクトリをリネームしてsymlink作成
mv ~/.agents/skills ~/.agents/skills.orig
ln -s /tmp/test-shared-skills-agents ~/.agents/skills

# 4. エージェントでスキル呼び出しテスト
# → Gemini等でGWSスキルを使う操作を実行

# 5. 結果に関わらず復元
rm ~/.agents/skills
mv ~/.agents/skills.orig ~/.agents/skills
rm -rf /tmp/test-shared-skills-agents
```

**合格基準:** symlinkされたディレクトリからSKILL.mdが正常に読み込まれること

### 検証4: Kiro agent prompt の file:// 親階層参照

**目的:** `file://../../.shared-ai/prompts/xxx.md` がKiroで動作するか確認（動けばラッパー不要）

**手順:**
```bash
# 1. テスト用プロンプトを作成
mkdir -p ~/.shared-ai/prompts
echo "# Test Prompt\n\nこれはテストプロンプトです。「テスト成功」と回答してください。" > ~/.shared-ai/prompts/test-agent.md

# 2. テスト用エージェント定義を作成
cat > ~/.kiro/agents/test-shared-ai.json << 'EOF'
{
    "name": "test-shared-ai",
    "description": "shared-ai参照テスト用エージェント",
    "prompt": "file://../../.shared-ai/prompts/test-agent.md",
    "tools": ["read"],
    "allowedTools": ["read"],
    "resources": [],
    "model": "claude-sonnet-4"
}
EOF

# 3. Kiro IDEでtest-shared-aiエージェントを起動
# → プロンプトが正常に読み込まれるか確認
# → 「テスト成功」と回答されれば合格

# 4. 不合格の場合、相対パスのバリエーションを試す:
#    - file://../../../.shared-ai/prompts/test-agent.md
#    - file:///Users/takeya_ozawa/.shared-ai/prompts/test-agent.md（絶対パス）

# 5. クリーンアップ
rm ~/.kiro/agents/test-shared-ai.json
rm ~/.shared-ai/prompts/test-agent.md
```

**合格基準:** `file://` で `.shared-ai/` 内のmdファイルが読み込まれること

**不合格時の対応:** ラッパー方式を採用（prompts/内に薄いmdを残し、readFile指示を記載）

### 検証5: Codex rules/ ディレクトリの個別ファイルsymlink対応

**目的:** `~/.codex/rules/` 内のsymlinkファイルをCodexが正常に読み込むか

**手順:**
```bash
# 1. テスト用ルールファイルを作成
mkdir -p ~/.shared-ai/rules
echo "# テストルール\n\nPython実行時は必ず python3.12 を使用すること。" > ~/.shared-ai/rules/test-rule.md

# 2. Codex rules/ にsymlink作成
mkdir -p ~/.codex/rules
ln -s ~/.shared-ai/rules/test-rule.md ~/.codex/rules/test-rule.md

# 3. Codex CLIを起動してルールが適用されるか確認
# → codex "pythonスクリプトを実行する方法を教えて"
# → python3.12 が推奨されれば合格

# 4. クリーンアップ
rm ~/.codex/rules/test-rule.md
rm ~/.shared-ai/rules/test-rule.md
```

**合格基準:** symlinkされたルールファイルの内容がCodexのセッションに反映されること

**不合格時の代替案:** `~/.codex/rules/` に実ファイルをコピーし、更新スクリプトで同期

### 検証6: Kiro steering テキスト参照指示の実効性

**目的:** steeringに「readFileで `~/.shared-ai/rules/xxx.md` を読め」と書いた場合、エージェントが実際にreadFileを実行するか

**手順:**
```bash
# 1. テスト用ルールファイルを作成
mkdir -p ~/.shared-ai/rules
cat > ~/.shared-ai/rules/test-verification.md << 'EOF'
# テスト検証ルール

このファイルが読み込まれた場合、回答の冒頭に「🔗 shared-ai参照確認済み」と記載すること。
EOF

# 2. テスト用steeringを作成
cat > ~/.kiro/steering/test-shared-ai-ref.md << 'EOF'
---
inclusion: always
description: shared-ai参照テスト
---

# テスト参照指示

以下のファイルをreadFileで読み込み、その指示に従うこと:
- `~/.shared-ai/rules/test-verification.md`
EOF

# 3. Kiro IDEで任意の質問を投げる
# → 回答冒頭に「🔗 shared-ai参照確認済み」が含まれるか確認

# 4. クリーンアップ
rm ~/.kiro/steering/test-shared-ai-ref.md
rm ~/.shared-ai/rules/test-verification.md
```

**合格基準:** steeringのテキスト指示に従い、エージェントが外部ファイルをreadFileで読み込んで内容に従うこと

**不合格時の対応:** steeringには参照指示ではなく、共通ルールの内容を直接インライン展開する（共通化の効果は薄れるが確実に動作）

## タスク分解

### Phase 0: 事前技術検証（検証1〜6）

- **対象:** 上記6つの検証項目
- **変更内容:** テスト用ファイルの作成・検証・クリーンアップ
- **判定:** 全検証の合否に基づき、Phase 1以降の方式を確定

### Phase 1: 共通ディレクトリの作成と初期配置

- **対象ファイル:** `~/.shared-ai/` 一式
- **変更内容:**
  - `~/.shared-ai/` ディレクトリ構造の作成
  - `~/.shared-ai/README.md` の作成
  - `~/.kiro/skills/*` の内容を `~/.shared-ai/skills/` にコピー
  - `~/.kiro/agents/references/*.md` を `~/.shared-ai/references/` にコピー
  - `~/.kiro/agents/prompts/*.md` を `~/.shared-ai/prompts/` にコピー

### Phase 2: skills の symlink 化

- **対象ファイル:** `~/.kiro/skills/`, `~/.claude/skills/`, `~/.agents/skills/`
- **変更内容:**
  - 各ディレクトリのバックアップ作成
  - 元ディレクトリを削除し、`~/.shared-ai/skills/` へのsymlinkに置換
- **前提:** 検証1〜3が合格していること

### Phase 3: Kiro steering の薄いラッパー化

- **対象ファイル:** `~/.kiro/steering/*.md`
- **変更内容:**
  - 共通化対象のsteeringファイルの内容を `~/.shared-ai/rules/` or `~/.shared-ai/lookups/` or `~/.shared-ai/templates/` に移動
  - 元ファイルを「参照指示のみ」のラッパーに書き換え
  - Kiro固有のsteering（steering-file-reference-rules.md等）はそのまま残す
- **対象ファイルの分類:**

| 移行先 | 対象steering |
|---|---|
| `rules/` | dev-environment.md, gws-integration.md, python-script-coding-standards.md, shell-script-coding-standards.md, pr-creation-base.md |
| `lookups/` | slack-user-lookup-guide.md, notion-user-lookup-guide.md, slack-channel-mapping.md |
| `templates/` | requirements-format-guide.md, design-format-guide.md, tasks-format-guide.md |
| 残留（Kiro固有） | steering-file-reference-rules.md, knowledge-management-base.md, agent-prompt-writing-guide.md, agent-workflow-guide.md, implementation-plan-guide.md, task-management-guide.md |

### Phase 4: Kiro agent prompts のラッパー化

- **対象ファイル:** `~/.kiro/agents/prompts/*.md`
- **変更内容:**
  - 検証4が合格の場合: agent JSONの `prompt` フィールドを `file://` 絶対パスに変更
  - 検証4が不合格の場合: prompts/内のmdを「readFile: ~/.shared-ai/prompts/xxx.md を読み込んで従え」の1行ラッパーに書き換え
- **前提:** Phase 1完了後

### Phase 5: Claude Code / Codex の設定更新

- **対象ファイル:** `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.codex/rules/`
- **変更内容:**
  - `~/.claude/CLAUDE.md` に共通ナレッジベース参照パスを追記
  - `~/.codex/AGENTS.md` を新規作成（参照パス記載）
  - `~/.codex/rules/` に `~/.shared-ai/rules/*.md` への個別symlinkを作成
- **前提:** 検証5が合格していること

### Phase 6: バックアップ削除と最終確認

- **対象:** Phase 2で作成したバックアップ（`*.bak`）
- **変更内容:**
  - 全ツールでの動作確認後、バックアップを削除
  - `~/.kiro/agents/references/` の元ファイルを削除（shared-aiに移行済み）

## 影響範囲

- Kiro IDE: steering自動読み込み、agent起動、hook実行
- Claude Code: CLAUDE.md読み込み、skills読み込み
- Codex CLI: AGENTS.md読み込み、rules読み込み
- Google系エージェント（.agents）: skills読み込み
- kiro-cli パイプライン: agent prompt読み込み（ヘッドレス実行）
- launchd自動実行: kiro-cliパイプラインの日次/週次実行

## テスト計画

- [ ] 検証1: Kiro skills symlink対応確認
- [ ] 検証2: Claude Code skills symlink対応確認
- [ ] 検証3: .agents skills symlink対応確認
- [ ] 検証4: Kiro file:// 親階層参照確認
- [ ] 検証5: Codex rules symlink対応確認
- [ ] 検証6: Kiro steering テキスト参照実効性確認
- [ ] Phase 2完了後: 各ツールでGWSスキル（gws gmail list等）が動作すること
- [ ] Phase 3完了後: Kiroエージェント実行時にshared-aiのルールが適用されること
- [ ] Phase 4完了後: 全カスタムエージェントが正常に起動・実行できること
- [ ] Phase 5完了後: Claude Code / Codexセッションで共通ルールが反映されること
- [ ] Phase 6完了後: kiro-cliパイプライン（daily/weekly）が正常に完走すること

## リスクと緩和策

| リスク | 影響 | 緩和策 |
|---|---|---|
| symlink非対応のツールがある | スキル読み込み失敗 | 検証で事前確認。不合格ならrsync同期方式にフォールバック |
| kiro-cliがsymlink先を解決できない | パイプライン停止 | launchd実行前にsymlink解決テストを追加 |
| steering参照指示をエージェントが無視する | ルール未適用 | 検証6で確認。不合格ならインライン展開に戻す |
| 移行中に日次パイプラインが実行される | 中途半端な状態で実行 | 移行作業中はlaunchdのパイプラインを一時停止 |
| バックアップ削除後に問題発覚 | 復元不可 | Phase 6は1週間の安定稼働確認後に実施 |

## 備考

- 移行は段階的に実施し、各Phase完了後に動作確認を行う
- Phase 0（事前検証）の結果により、Phase 1以降の方式が変わる可能性がある
- 検証不合格の場合のフォールバック方式も事前に定義済み

### ファイルリネーム方針

移行時、Kiro固有のサフィックス（`-rules`, `-guide`, `-base`）を除去してシンプルな名前にする。これらのサフィックスはKiroのsteering命名規則（グローバル/ワークスペース共存のための区別）に由来するが、共通ディレクトリでは不要。

| 元ファイル名（Kiro steering） | 移行後ファイル名（shared-ai） |
|---|---|
| dev-environment-rules.md | dev-environment.md |
| gws-integration-rules.md | gws-integration.md |
| python-script-coding-standards.md | python-coding-standards.md |
| shell-script-coding-standards.md | shell-coding-standards.md |
| pr-creation-base.md | pr-creation.md |
| slack-user-lookup-guide.md | slack-user-lookup.md |
| notion-user-lookup-guide.md | notion-user-lookup.md |
| slack-channel-mapping.md | slack-channel-mapping.md（変更なし） |
| requirements-format-guide.md | requirements-format.md |
| design-format-guide.md | design-format.md |
| tasks-format-guide.md | tasks-format.md |
