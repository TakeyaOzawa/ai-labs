# AI Development Environment — dotfiles

## 1. 概要

### 1.1 目的

本リポジトリは、複数のAIコーディングツール（Kiro / Claude Code / Codex CLI / Gemini / .agents）の設定ファイルを一元管理し、ツール間でルール・プロンプト・スキルの一貫性を保つためのdotfiles管理基盤である。

### 1.2 対象読者

- 本環境の利用者（セットアップ・日常運用）
- AIエージェントの開発・保守担当者

### 1.3 適用範囲

| 管理対象 | 含む | 含まない |
|---|---|---|
| AIツール設定 | steering, prompts, skills, hooks, agents | ツール本体のインストール |
| 共通ナレッジ | rules, lookups, templates, references | 業務データ（Documents/works/） |
| ユーティリティ | scripts/ 配下のスクリプト | アプリケーションコード |

## 2. 前提条件

### 2.1 動作環境

| 項目 | 要件 | 備考 |
|---|---|---|
| OS | macOS 13+ / Linux (Ubuntu 22.04+) | WindowsはWSL2経由で利用 |
| Python | 3.12 (`python3.12` で実行可能) | 3.13はSSL互換性問題あり |
| Git | 2.30+ | |
| シェル | zsh (macOS) / bash (Linux) | |

### 2.2 Windows利用時の前提

WSL2（Windows Subsystem for Linux 2）を使用する。WSL2内はLinux環境として動作するため、上記のLinux要件が適用される。

```powershell
# WSL2インストール（PowerShell 管理者権限）
wsl --install
```

### 2.3 依存するツール（任意）

| ツール | 用途 | 必須/任意 |
|---|---|---|
| Kiro IDE | AI開発環境 | 任意 |
| Claude Code | AIコーディング支援 | 任意 |
| Codex CLI | AIコーディング支援 | 任意 |
| Gemini CLI | AIコーディング支援 | 任意 |
| GWS CLI (`gws`) | Google Workspace操作 | 任意（skills利用時） |

## 3. セットアップ

### 3.1 初回セットアップ

```bash
# 1. clone
git clone <repo-url> ~

# 2. symlink構築
python3.12 ~/scripts/setup-shared-ai.py

# 3. 検証
python3.12 ~/scripts/setup-shared-ai.py --verify
```

### 3.2 セットアップスクリプトの動作

`~/scripts/setup-shared-ai.py` は以下のsymlinkを作成する:

| リンクパス | ターゲット | 種別 |
|---|---|---|
| `~/.kiro/skills/` | `~/.shared-ai/skills/` | ディレクトリ |
| `~/.claude/skills/` | `~/.shared-ai/skills/` | ディレクトリ |
| `~/.agents/skills/` | `~/.shared-ai/skills/` | ディレクトリ |
| `~/.codex/rules/*.md` | `~/.shared-ai/rules/*.md` | 個別ファイル |

オプション:
- `--dry-run` — 実行内容の確認のみ（変更なし）
- `--verify` — 現在のsymlink状態を検証

### 3.3 Git管理上の制約

symlinkは `.gitignore` で除外されており、Gitには記録されない。clone後は必ずセットアップスクリプトを実行すること。

## 4. アーキテクチャ

### 4.1 設計原則

| 原則 | 説明 |
|---|---|
| Single Source of Truth | `~/.shared-ai/` が全ツール共通ナレッジの唯一の実体 |
| 既存機構の非破壊 | 各ツールの読み込み機構は変更しない。ファイルシステムレベルで間接参照を実現 |
| 冪等性 | セットアップ・更新操作は何度実行しても同じ結果 |
| 軽量ラッパー | `.kiro/steering/`, `.kiro/hooks/`, `.kiro/agents/` は薄いラッパーに徹し、本体は `.shared-ai/` に配置する |
| agents-prompts 1:1対応 | `.kiro/agents/{name}.json` と `.shared-ai/prompts/{name}.md` は必ず1:1で対応する |
| ガイド分離 | プロンプト内の再利用可能なルール・手順は `.shared-ai/references/` に切り出し、プロンプトからreadFileで参照する |
| steering優先 | kiro-cliではhookが発火しないため、steeringで実現できることはsteeringで実装する。hookはIDE固有のイベント駆動が必須な場合のみ |

### 4.2 参照方式

| ツール | 対象 | 方式 | 理由 |
|---|---|---|---|
| Kiro | steering | テキスト参照（Wrapper_File） | `#[[file:]]` が親階層非対応 |
| Kiro | skills | ディレクトリsymlink | skills自動検出機構を利用 |
| Kiro | agent prompts | `file://` 相対パス | agent JSONから直接参照 |
| Claude Code | rules | テキスト参照（CLAUDE.md） | グローバル設定ファイルに列挙 |
| Claude Code | skills | ディレクトリsymlink | skills自動検出機構を利用 |
| Codex CLI | rules | 個別ファイルsymlink | `~/.codex/rules/` 自動読み込み |
| Codex CLI | 全般 | テキスト参照（AGENTS.md） | グローバル設定ファイルに列挙 |
| Gemini | 全般 | テキスト参照（GEMINI.md） | グローバル設定ファイルに列挙 |
| .agents | skills | ディレクトリsymlink | skills自動検出機構を利用 |

### 4.3 構成図

```
~/.shared-ai/ (Single Source of Truth)
├── rules/       ──→ Kiro(Wrapper) / Codex(symlink) / Claude(CLAUDE.md) / Gemini(GEMINI.md)
├── lookups/     ──→ Kiro(Wrapper)
├── prompts/     ──→ Kiro(file://) / kiro-cli(file://)
├── references/  ──→ Kiro(readFile)
├── interfaces/  ──→ Kiro(readFile)
├── templates/   ──→ Kiro(Wrapper)
└── skills/      ──→ Kiro(symlink) / Claude(symlink) / .agents(symlink)
```

## 5. ディレクトリ構成

### 5.1 構成アイテム一覧

```
~/
├── .shared-ai/            # 共通ナレッジベース（実体）
│   ├── rules/             #   行動制約（コーディング規約等）
│   ├── lookups/           #   マスタデータ（ID逆引き等）
│   ├── prompts/           #   エージェントプロンプト（薄いラッパー）
│   ├── references/        #   設計ガイド・手順書（本体）
│   ├── interfaces/        #   エージェントの出力フォーマット・入力リソース定義
│   ├── templates/         #   新規ファイル作成時の雛形
│   └── skills/            #   共通スキル（GWS CLI等）
├── .kiro/                 # Kiro IDE設定
│   ├── agents/            #   エージェント定義（JSON）
│   ├── hooks/             #   エージェントhook
│   ├── steering/          #   Wrapper_File（→ .shared-ai参照）
│   ├── settings/          #   IDE設定（mcp.json）
│   └── specs/             #   spec（設計ドキュメント）
├── .claude/               # Claude Code設定
│   └── CLAUDE.md          #   行動ルール（→ .shared-ai参照）
├── .codex/                # Codex CLI設定
│   └── AGENTS.md          #   行動ルール（→ .shared-ai参照）
├── .gemini/               # Gemini CLI設定
│   └── GEMINI.md          #   行動ルール（→ .shared-ai参照）
├── .agents/               # Google系エージェント設定
├── scripts/               # ユーティリティスクリプト
├── issues/                # 実装プラン
└── Documents/works/       # 作業データ（Git管理外）
```

### 5.2 依存関係

```
.kiro/steering/*.md ─── readFile ───→ .shared-ai/rules/
.kiro/steering/*.md ─── readFile ───→ .shared-ai/lookups/
.kiro/steering/*.md ─── readFile ───→ .shared-ai/templates/
.kiro/agents/*.json ─── file:// ────→ .shared-ai/prompts/
.kiro/skills/       ─── symlink ────→ .shared-ai/skills/
.claude/skills/     ─── symlink ────→ .shared-ai/skills/
.agents/skills/     ─── symlink ────→ .shared-ai/skills/
.codex/rules/*.md   ─── symlink ────→ .shared-ai/rules/
```

## 6. 運用手順

### 6.1 ルール・プロンプトの変更

`~/.shared-ai/` 内のファイルを直接編集する。変更は全ツールに自動反映される。

```bash
vim ~/.shared-ai/rules/python-coding-standards.md
```

### 6.2 新しいルールの追加

1. `~/.shared-ai/rules/` にmdファイルを作成
2. 各ツールの参照設定を追加:
   - Kiro: `~/.kiro/steering/` にWrapper_Fileを作成
   - Codex: `ln -s ~/.shared-ai/rules/xxx.md ~/.codex/rules/xxx.md` + `setup-shared-ai.py` に定義追加
   - Claude Code: `~/.claude/CLAUDE.md` に参照パスを追記
   - Gemini: `~/.gemini/GEMINI.md` に参照パスを追記

### 6.3 スキルの追加

`~/.shared-ai/skills/` にディレクトリを作成するだけ。symlinkにより全ツールから自動アクセス可能。

### 6.4 エージェントの追加

1. `~/.shared-ai/prompts/` にプロンプトmdを作成
2. `~/.kiro/agents/` にagent JSONを作成（`prompt: "file://../../.shared-ai/prompts/xxx.md"`）

## 7. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| スキルが認識されない | symlinkが切れている | `python3.12 ~/scripts/setup-shared-ai.py` を再実行 |
| steeringのルールが適用されない | Wrapper_Fileの参照パスが誤り | `~/.kiro/steering/` 内のWrapper_Fileを確認 |
| Codexでルールが反映されない | symlinkが存在しない | `ls -la ~/.codex/rules/` で確認し、不足分を作成 |
| agent起動時にプロンプトが空 | file://パスの解決失敗 | agent JSONの `prompt` フィールドのパスを確認 |
| hookからのagent実行が失敗 | hookが旧パスを参照 | hook内のパスが `.shared-ai/prompts/` を指しているか確認 |

## 8. 既知の制約

現時点で未解消の制約はなし。

## 9. 関連ドキュメント

| ドキュメント | 内容 |
|---|---|
| [.shared-ai/README.md](.shared-ai/README.md) | 共通ナレッジベースの詳細（ディレクトリ構造、リネームマッピング、Wrapper_Fileフォーマット） |
| [.kiro/specs/shared-ai-knowledge-base/](.kiro/specs/shared-ai-knowledge-base/) | 移行の要件定義・設計・タスク |
| [issues/shared-ai-knowledge-base.md](issues/shared-ai-knowledge-base.md) | 移行の実装プラン |

## 10. 変更履歴

| 日付 | 内容 |
|---|---|
| 2026-05-10 | web-searcher新規作成。agent-pipeline-creator新規作成。interfaces/切り出し。Gemini CLI対応。ai-architecture-guide.md作成。agent-creator行動原則強化（固有名排除・Slack通知委譲・allowedPaths網羅）。scoutレポート曜日計算をシェルコマンドで確定する方式に修正 |
| 2026-05-09 | hookパス更新、prompts/references元ファイル削除、テンプレート/ガイド分離、レビュアー強化 |
| 2026-05-09 | 初版作成。shared-ai移行完了に伴いREADME整備 |
