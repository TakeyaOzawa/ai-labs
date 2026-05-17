# agent-params-schema: エージェント起動パラメータ体系の導入

## 変更種別

feat

## 概要

- エージェント起動時に構造化されたパラメータ（`agent_params` YAMLブロック）を渡す仕組みを定義する
- `agent-common.md` にパラメータ解析ロジックを追加し、IDE対話時の確認フローを実装する
- パラメータスキーマを `interfaces/agent-params-schema.md` として文書化する

## 問題・背景

- 現状、エージェントの振る舞い制御（Slack通知の要否、出力先等）はプロンプトテキスト内の文言解析に依存している
- 文言の微妙な変更で判定が壊れる脆弱性がある
- 呼び出し側が何を制御できるか不明確
- 新しい制御パラメータ追加のたびにプロンプト解析ロジックが増える

## 修正対象

- `~/.shared-ai/interfaces/agent-params-schema.md`（新規）
- `~/.shared-ai/references/agent-common.md`（パラメータ解析セクション追加）

## タスク分解

### Task 1: agent-params-schema.md の作成

- **対象ファイル:** `~/.shared-ai/interfaces/agent-params-schema.md`（新規）
- **変更内容:** エージェント起動パラメータの完全なスキーマ定義。input/output の全フィールド、デフォルト値、型制約を記載。パラメータ解決の優先順位ルール、呼び出し側（パイプライン、dispatch-wrapper、手動）ごとの典型的なステップ定義例を含む

### Task 2: agent-common.md へのパラメータ解決ロジック追加

- **対象ファイル:** `~/.shared-ai/references/agent-common.md`
- **変更内容:** 「§0 agent_params の解析」セクションを追加。プロンプト冒頭のYAMLブロック解析手順、デフォルト値適用ルール、`agent_params` ブロック未検出時（IDE対話時）のユーザー確認フローを記載

### Task 3: IDE対話時の確認フロー定義

- **対象ファイル:** `~/.shared-ai/references/agent-common.md`
- **変更内容:** `agent_params` ブロック不在時の確認フロー追加。デフォルト値（slack: 必要/compact、log: 不要、job: 不要）を明記。確認後に `notify-slack.py` を直接実行する手順を記載

## 設計方針

### パラメータ渡し方式

プロンプト冒頭に `---` で囲んだYAMLブロックとして渡す。エージェントに渡すのは `input` と `output` のみ。`log`, `slack`, `job` はパイプラインランナーが消費するパラメータであり、エージェントには渡さない。

```yaml
---
agent_params:
  input:
    source_type: file
    source_path: "Documents/works/scout_reports/tech_trends/daily/2026-05-16_tech_trends.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
  output:
    enabled: true
    path: "Documents/works/research_materials/2026-05-17_deno-2-node-compat.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
---
```

### パラメータ解決の優先順位

1. 明示的パラメータ（プロンプト冒頭のYAMLブロック）
2. agent-common.md に定義されたデフォルト値（未指定フィールドのみ）
3. YAMLブロック不在時（IDE対話）→ ユーザーに確認フローを実行

### 責務分離

| パラメータ | エージェントに渡す | ランナーが消費 | 理由 |
|---|---|---|---|
| `input.*` | ✅ | ✅ | エージェントが入力ソースを知る必要あり |
| `output.*` | ✅ | ✅ | エージェントが出力先・フォーマットを知る必要あり |
| `log.*` | ❌ | ✅ | ランナーがログファイルにリダイレクト |
| `slack.*` | ❌ | ✅ | ランナーが通知実行 |
| `job.*` | ❌ | ✅ | ランナーがジョブ更新 |

## 影響範囲

- `agent-common.md` を参照する全エージェント（28ファイル）
- パイプラインランナー（`_pipeline_common.py`）— YAMLブロック生成ロジックの追加が必要（別issue: pipeline-redesign で対応）

## テスト計画

- [ ] agent-params-schema.md のスキーマが全パラメータを網羅していること
- [ ] agent-common.md のパラメータ解析セクションが3KB制限を超えないこと（超える場合はschemaへの参照で代替）
- [ ] IDE対話時のSlack通知デフォルトが「必要（compact）」で動作すること
- [ ] `agent_params` ブロックなしでエージェントを呼び出した場合、ユーザーにinput/outputの確認が行われること

## 前提・依存

- `extract-agent-common-module` issue の Task 1〜6 が完了していること（完了済み）
- パイプラインスクリプト側の対応は `pipeline-redesign` issue で実施
