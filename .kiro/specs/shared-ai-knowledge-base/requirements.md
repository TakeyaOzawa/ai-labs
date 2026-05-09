---
spec_type: refactor
feature_name: shared-ai-knowledge-base
status: active
created_at: 2026-05-01
created_by: kiro
updated_at: 2026-05-08
updated_by: kiro
related_domain: []
---

# 要件定義書

## 1. はじめに

### 1.1 目的

Kiro / Claude Code / Codex CLI の3つのAIツール間で重複管理されているmdファイル（ルール、プロンプト、参照データ、スキル）を `~/.shared-ai/` に集約し、各ツールからsymlinkまたはテキスト参照で利用する構造に移行する。

### 1.2 背景と動機

- 同一内容のファイルが `~/.kiro/steering/`, `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` に分散・重複している
- GWSスキルは `~/.kiro/skills/`, `~/.claude/skills/`, `~/.agents/skills/` に完全同一の内容が3重に配置されている
- ルール変更時に3箇所を手動で同期する必要があり、不整合が発生しやすい
- 新しいAIツールを導入する際に、毎回全ルールをコピーする必要がある

### 1.3 スコープ

- `~/.shared-ai/` ディレクトリの新規作成と初期配置
- skills ディレクトリのsymlink化（Kiro / Claude Code / .agents）
- Kiro steering の薄いラッパー化（テキスト参照指示方式）
- Kiro agent prompts のラッパー化
- Claude Code / Codex の設定更新（参照パス追記、rules symlink）
- バックアップ削除と最終確認

### 1.4 変更の性質

- [x] 既存機能の追加・変更（既存の設定ファイル群を再構成し、参照方式を変更）

### 1.5 用語集

| 用語 | 定義 | 利用例 | 控える表現 | 備考 |
| --- | --- | --- | --- | --- |
| Shared_AI_Directory | `~/.shared-ai/` に配置される共通ナレッジベースディレクトリ | Shared_AI_Directoryにルールを集約する | 共通フォルダ | 全AIツールから参照される単一の真実の源 |
| Steering_File | Kiroがセッション開始時に自動読み込みするmdファイル | Steering_Fileにテキスト参照指示を記載する | 設定ファイル | `~/.kiro/steering/` 配下に配置 |
| Symlink | ファイルシステムのシンボリックリンク | skills ディレクトリをSymlinkで参照する | ショートカット | `ln -s` で作成 |
| Wrapper_File | 実体ファイルへの参照指示のみを含む薄いmdファイル | Steering_FileをWrapper_Fileに書き換える | 中継ファイル | 実体は Shared_AI_Directory に存在 |
| Text_Reference | Steering_File内に記載する「readFileで外部ファイルを読め」という指示 | Text_Referenceで共通ルールを参照する | テキスト参照 | symlink非対応の場合の代替方式 |
| Migration_Script | ファイル移動・symlink作成を自動化するシェルスクリプト | Migration_Scriptで一括移行する | 移行ツール | Phase実行時に使用 |

### 1.6 参照文書

- Issue: `/Users/takeya_ozawa/issues/shared-ai-knowledge-base.md`

## 2. リファクタリング概要

### 2.1 現行構造

現在、AIツール設定ファイルは以下のように分散配置されている:

```
~/.kiro/
├── steering/          # Kiro行動ルール（11ファイル）
├── skills/            # GWSスキル（40+ディレクトリ）
└── agents/
    ├── prompts/       # エージェントプロンプト
    └── references/    # 参照データ

~/.claude/
├── CLAUDE.md          # Claude Code行動ルール
└── skills/            # GWSスキル（kiroと同一内容）

~/.agents/
└── skills/            # GWSスキル（kiroと同一内容）

~/.codex/
└── AGENTS.md          # Codex行動ルール
```

### 2.2 変更方針

参照方式をファイル種別ごとに使い分け、`~/.shared-ai/` を単一の真実の源（Single Source of Truth）とする:

| 対象 | 方式 | 理由 |
|---|---|---|
| skills | ディレクトリsymlink | 各ツールが `~/.xxx/skills/` を直接読み込む機構を持つため |
| Codex rules | 個別ファイルsymlink | Codexが `~/.codex/rules/*.md` を自動読み込みするため |
| Kiro steering | テキスト参照指示 | `#[[file:]]` が親階層非対応。`inclusion: always` で指示を自動注入 |
| Claude Code CLAUDE.md | テキスト参照指示 | グローバルCLAUDE.mdに参照パスを列挙 |
| Codex AGENTS.md | テキスト参照指示 | グローバルAGENTS.mdに参照パスを列挙 |
| Kiro agent prompts | ラッパー方式 | `file://./prompts/xxx.md` の制約上、prompts/内に薄いラッパーを残す |

移行後のディレクトリ構造:

```
~/.shared-ai/
├── README.md
├── rules/                      # 行動ルール（全ツール共通）
├── lookups/                    # データ参照ガイド
├── prompts/                    # エージェントプロンプト本体
├── references/                 # 参照データ
├── templates/                  # フォーマットガイド
└── skills/                     # 共通スキル（GWS等）
```

### 2.3 互換性

- 各AIツールの既存の読み込み機構（skills自動検出、steering自動注入、CLAUDE.md読み込み等）は変更しない
- symlink非対応が判明した場合はrsync同期方式にフォールバックする
- 移行中はlaunchdパイプラインを一時停止し、中途半端な状態での実行を防止する
- Phase 6（バックアップ削除）は1週間の安定稼働確認後に実施する

## 3. 機能要件

### REQ-1: 事前技術検証

**ユーザーストーリー:** 運用者として、各AIツールのsymlink対応・テキスト参照対応を事前に検証したい。そうすることで、移行方式を確定し、不合格時のフォールバック方式を選択できる。

**優先度:** 高

#### 受入基準

1. WHEN Kiro skills ディレクトリをsymlinkに置き換えた場合 THEN THE Migration_Script SHALL symlink先のSKILL.mdからスキルが正常に読み込まれることを確認する
2. WHEN Claude Code skills ディレクトリをsymlinkに置き換えた場合 THEN THE Migration_Script SHALL symlink先のSKILL.mdからスキルが正常に読み込まれることを確認する
3. WHEN .agents/skills ディレクトリをsymlinkに置き換えた場合 THEN THE Migration_Script SHALL symlink先のSKILL.mdからスキルが正常に読み込まれることを確認する
4. WHEN Kiro agent prompt で file:// 親階層参照を使用した場合 THEN THE Migration_Script SHALL プロンプトが正常に読み込まれるか否かを判定する
5. WHEN Codex rules/ 内にsymlinkファイルを配置した場合 THEN THE Migration_Script SHALL symlinkされたルールファイルの内容がセッションに反映されることを確認する
6. WHEN Kiro steering にテキスト参照指示を記載した場合 THEN THE Migration_Script SHALL エージェントが外部ファイルをreadFileで読み込んで内容に従うことを確認する
7. IF いずれかの検証が不合格となった場合 THEN THE Migration_Script SHALL 該当項目のフォールバック方式を記録し、Phase 1以降の方式を切り替える

### REQ-2: 共通ディレクトリの作成と初期配置

**ユーザーストーリー:** 運用者として、`~/.shared-ai/` に全AIツール共通のナレッジベースを構築したい。そうすることで、ルール・プロンプト・スキルの単一管理が可能になる。

**優先度:** 高

#### 受入基準

1. WHEN Migration_Script を実行した場合 THEN THE Shared_AI_Directory SHALL `rules/`, `lookups/`, `prompts/`, `references/`, `templates/`, `skills/` のサブディレクトリを含む構造で作成される
2. WHEN Migration_Script を実行した場合 THEN THE Shared_AI_Directory SHALL 構造説明と各ツールからの参照方法を記載したREADME.mdを含む
3. WHEN steering ファイルを移行する場合 THEN THE Migration_Script SHALL Kiro固有のサフィックス（-rules, -guide, -base）を除去したファイル名で配置する
4. WHEN skills を移行する場合 THEN THE Migration_Script SHALL 全GWSスキルディレクトリを `~/.shared-ai/skills/` に完全にコピーする
5. WHEN prompts を移行する場合 THEN THE Migration_Script SHALL `~/.kiro/agents/prompts/` 配下の全mdファイルを `~/.shared-ai/prompts/` にコピーする
6. WHEN references を移行する場合 THEN THE Migration_Script SHALL `~/.kiro/agents/references/` 配下の全mdファイルを `~/.shared-ai/references/` にコピーする

### REQ-3: skills の symlink 化

**ユーザーストーリー:** 運用者として、3箇所に重複配置されているGWSスキルをsymlinkで一元化したい。そうすることで、スキル更新時の同期作業が不要になる。

**優先度:** 高

#### 受入基準

1. WHEN symlink化を実行する前に THEN THE Migration_Script SHALL 各ツールのskillsディレクトリのバックアップを作成する
2. WHEN symlink化を実行した場合 THEN THE Migration_Script SHALL `~/.kiro/skills/` を `~/.shared-ai/skills/` へのsymlinkに置換する
3. WHEN symlink化を実行した場合 THEN THE Migration_Script SHALL `~/.claude/skills/` を `~/.shared-ai/skills/` へのsymlinkに置換する
4. WHEN symlink化を実行した場合 THEN THE Migration_Script SHALL `~/.agents/skills/` を `~/.shared-ai/skills/` へのsymlinkに置換する
5. IF REQ-1の検証1〜3のいずれかが不合格の場合 THEN THE Migration_Script SHALL 該当ツールのskillsはsymlink化せず、rsync同期方式を採用する

### REQ-4: Kiro steering の薄いラッパー化

**ユーザーストーリー:** 運用者として、Kiro steeringの共通ルールをShared_AI_Directoryから参照する方式に変更したい。そうすることで、ルール変更時にKiro steering側の更新が不要になる。

**優先度:** 高

#### 受入基準

1. WHEN 共通化対象のsteering ファイルを移行する場合 THEN THE Migration_Script SHALL ファイル内容を `~/.shared-ai/` の対応サブディレクトリに移動する
2. WHEN 共通化対象のsteering ファイルを移行した場合 THEN THE Migration_Script SHALL 元ファイルをText_Referenceのみを含むWrapper_Fileに書き換える
3. THE Wrapper_File SHALL `inclusion: always` のfront-matterと、readFileで対応するShared_AI_Directoryファイルを読み込む指示を含む
4. WHEN Kiro固有のsteering（steering-file-reference-rules.md, knowledge-management-base.md等）を処理する場合 THEN THE Migration_Script SHALL 移行せずそのまま残す
5. IF REQ-1の検証6が不合格の場合 THEN THE Migration_Script SHALL テキスト参照指示ではなく、共通ルールの内容をインライン展開する方式を採用する

### REQ-5: Kiro agent prompts のラッパー化

**ユーザーストーリー:** 運用者として、Kiro agentのプロンプト本体をShared_AI_Directoryに集約したい。そうすることで、プロンプト更新時の管理が一元化される。

**優先度:** 中

#### 受入基準

1. WHILE REQ-1の検証4が合格している場合 THEN THE Migration_Script SHALL agent JSONの `prompt` フィールドを `file://` 絶対パスに変更する
2. IF REQ-1の検証4が不合格の場合 THEN THE Migration_Script SHALL prompts/内のmdを「readFile: ~/.shared-ai/prompts/xxx.md を読み込んで従え」の1行ラッパーに書き換える
3. WHEN ラッパー化を実行した場合 THEN THE Migration_Script SHALL 全カスタムエージェントが正常に起動・実行できることを確認する

### REQ-6: Claude Code / Codex の設定更新

**ユーザーストーリー:** 運用者として、Claude CodeとCodexからもShared_AI_Directoryの共通ルールを参照できるようにしたい。そうすることで、3ツール間でルールの一貫性が保たれる。

**優先度:** 中

#### 受入基準

1. WHEN Claude Code の設定を更新する場合 THEN THE Migration_Script SHALL `~/.claude/CLAUDE.md` にShared_AI_Directoryの参照パスを追記する
2. WHEN Codex の設定を更新する場合 THEN THE Migration_Script SHALL `~/.codex/AGENTS.md` を新規作成し、Shared_AI_Directoryの参照パスを記載する
3. WHEN Codex rules を設定する場合 THEN THE Migration_Script SHALL `~/.codex/rules/` に `~/.shared-ai/rules/*.md` への個別symlinkを作成する
4. IF REQ-1の検証5が不合格の場合 THEN THE Migration_Script SHALL `~/.codex/rules/` に実ファイルをコピーし、更新スクリプトで同期する方式を採用する

### REQ-7: バックアップ削除と最終確認

**ユーザーストーリー:** 運用者として、移行完了後に不要なバックアップを削除し、全ツールの正常動作を最終確認したい。そうすることで、ディスク使用量の無駄を排除し、移行の完了を確定できる。

**優先度:** 低

#### 受入基準

1. WHILE 全ツールが1週間安定稼働した状態で THEN THE Migration_Script SHALL Phase 2で作成したバックアップ（*.bak）を削除する
2. WHEN バックアップ削除を実行する前に THEN THE Migration_Script SHALL 全ツールでの動作確認チェックリストを実行する
3. WHEN 最終確認を実行する場合 THEN THE Migration_Script SHALL kiro-cliパイプライン（daily/weekly）が正常に完走することを確認する

### REQ-8: 移行中の安全性確保

**ユーザーストーリー:** 運用者として、移行作業中にパイプラインが中途半端な状態で実行されることを防ぎたい。そうすることで、移行中のデータ破損や実行エラーを回避できる。

**優先度:** 高

#### 受入基準

1. WHEN 移行作業を開始する前に THEN THE Migration_Script SHALL launchdのパイプライン（daily/weekly）を一時停止する
2. WHEN 移行作業が完了した場合 THEN THE Migration_Script SHALL launchdのパイプラインを再開する
3. IF 移行作業中にエラーが発生した場合 THEN THE Migration_Script SHALL バックアップから元の状態に復元する手順を提供する

## 4. 非機能要件

- パフォーマンス: symlink解決によるファイル読み込み遅延は無視できるレベル（ファイルシステム操作のため）
- 信頼性: 各Phase完了後に動作確認を実施し、問題発覚時はバックアップから復元可能
- 保守性: 共通ルールの変更が1箇所で完結し、全ツールに自動反映される構造を実現する
- セキュリティ: 該当なし（ローカルファイルシステム内の操作のみ）

## 5. 検証方法

| 要件ID | 受入基準 | 検証方法 | 検証内容 |
| --- | --- | --- | --- |
| REQ-1 | 1〜6 | テスト | 各検証項目のスクリプトを実行し、合否を判定 |
| REQ-1 | 7 | レビュー | フォールバック方式の記録を確認 |
| REQ-2 | 1〜6 | テスト | ディレクトリ構造・ファイル存在・内容の確認 |
| REQ-3 | 1〜4 | テスト | symlink作成後に各ツールでスキル呼び出しテスト |
| REQ-3 | 5 | レビュー | フォールバック方式の適用を確認 |
| REQ-4 | 1〜3 | テスト | Wrapper_File経由でルールが適用されることを確認 |
| REQ-4 | 4 | レビュー | Kiro固有ファイルが残留していることを確認 |
| REQ-4 | 5 | レビュー | フォールバック方式の適用を確認 |
| REQ-5 | 1〜3 | テスト | エージェント起動・実行テスト |
| REQ-6 | 1〜3 | テスト | 各ツールセッションでルール反映を確認 |
| REQ-6 | 4 | レビュー | フォールバック方式の適用を確認 |
| REQ-7 | 1〜3 | テスト | パイプライン完走確認 |
| REQ-8 | 1〜3 | テスト | launchd停止/再開の確認 |

## 6. 影響範囲

### 6.1 影響を受ける既存機能

- Kiro IDE: steering自動読み込み、agent起動、hook実行
- Claude Code: CLAUDE.md読み込み、skills読み込み
- Codex CLI: AGENTS.md読み込み、rules読み込み
- Google系エージェント（.agents）: skills読み込み
- kiro-cli パイプライン: agent prompt読み込み（ヘッドレス実行）
- launchd自動実行: kiro-cliパイプラインの日次/週次実行

### 6.2 リグレッションリスク

| リスク箇所 | リスク内容 | 確認方法 |
| --- | --- | --- |
| Kiro skills読み込み | symlink先を解決できずスキル認識失敗 | 検証1で事前確認 + Phase 2後にGWSスキル実行テスト |
| Claude Code skills読み込み | symlink先を解決できずスキル認識失敗 | 検証2で事前確認 + Phase 2後にスキル実行テスト |
| kiro-cli パイプライン | symlink先解決失敗でパイプライン停止 | Phase 4後にdaily/weeklyパイプライン実行テスト |
| Kiro steering読み込み | Wrapper_Fileの参照指示をエージェントが無視 | 検証6で事前確認 + Phase 3後にルール適用テスト |
| launchd実行 | 移行中に中途半端な状態で実行 | 移行前にlaunchd一時停止 |

### 6.3 後方互換性

- API互換性: 該当なし（ローカルファイル操作のみ）
- データ互換性: ファイル内容は変更せず、配置場所と参照方式のみ変更
- UI互換性: 該当なし

## 7. スコープ外

- AIツール本体のコード変更（Kiro/Claude Code/Codexのソースコード修正は行わない）
- 新規ルール・プロンプトの作成（既存ファイルの移行のみ）
- rsync同期スクリプトの自動実行設定（フォールバック時は手動実行で対応）
- ワークスペース固有のsteering（`.kiro/steering/` のプロジェクト固有ファイル）の移行
