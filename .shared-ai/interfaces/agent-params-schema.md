# agent_params スキーマ定義

エージェント起動時にプロンプト冒頭のYAMLブロックとして渡す構造化パラメータの仕様。

## YAMLブロック形式

プロンプト冒頭に `---` で囲んで記述する:

```yaml
---
agent_params:
  input:
    source_type: file | theme | url | none
    source_path: "{相対パス}"
    format_ref: "{interfaces/のパス}"
  output:
    enabled: true | false
    path: "{出力先相対パス}"
    format_ref: "{interfaces/のパス}"
---
```

## フィールド定義

### input（エージェントへの入力指定）

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `source_type` | enum | ✅ | — | 入力ソースの種別: `file`, `theme`, `url`, `none` |
| `source_path` | string | 条件付き | — | `source_type: file` 時に必須。`~` 始まりまたは相対パス |
| `source_theme` | string | 条件付き | — | `source_type: theme` 時に必須。テーマ文字列 |
| `source_url` | string | 条件付き | — | `source_type: url` 時に必須。調査起点URL |
| `format_ref` | string | ❌ | — | 入力フォーマット定義への参照パス（`~/.shared-ai/interfaces/` 配下） |

### output（エージェントの出力指定）

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `enabled` | boolean | ❌ | `true` | ファイル出力を行うか |
| `path` | string | 条件付き | テンプレート生成 | `enabled: true` 時に必須。出力先パス |
| `format_ref` | string | ❌ | — | 出力フォーマット定義への参照パス（`~/.shared-ai/interfaces/` 配下） |

`path` 未指定時のデフォルトテンプレート: `~/Documents/works/{agent_category}/{YYYYMMDD}_{summary}.md`
- `{agent_category}`: エージェント名から推定（例: `web-searcher` → `research_materials`）
- `{YYYYMMDD}`: 基準日付
- `{summary}`: 依頼内容の要約（kebab-case、最大30文字）

### ランナー専用パラメータ（エージェントには渡さない）

以下はパイプラインランナー（`_pipeline_common.py`）が消費する。エージェントのYAMLブロックには含まれない。

#### log（同期実行）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | boolean | `true` | ログファイル出力の有無 |
| `path` | string | `~/logs/{agent_name}/{YYYYMMDD}_{summary}.log` | ログ出力先パス |
| `level` | enum | `info` | `debug`: 全ステップ / `info`: 開始・完了のみ / `error`: エラー時のみ |

#### slack（非同期実行 — `notify-slack.py` を別プロセスで起動）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | boolean | `true` | Slack通知の有無 |
| `channel` | string | `${SLACK_DISPATCH_DM_CHANNEL}` | 通知先チャンネルID |
| `thread_mode` | enum | `compact` | `compact`: H1を親+残りスレッド / `sequential`: 分割順次投稿 |
| `thread_ts` | string | null | 既存スレッドに返信する場合のタイムスタンプ（指定時は thread_mode を無視） |
| `source` | enum | `output` | `output`: output.path のファイルを通知 / `text`: source_text を通知 |
| `source_text` | string | null | `source: text` 時の通知テキスト |
| `token_env` | string | `MY_SLACK_OAUTH_TOKEN` | Slack Bot Tokenの環境変数名 |
| `level` | enum | `info` | `debug`: 全ステップ通知 / `info`: 完了時のみ / `error`: エラー時のみ |

notify-slack.py CLI引数との対応:

| フィールド | CLI引数 |
|---|---|
| `channel` | `--channel` |
| `thread_mode` / `thread_ts` | `--thread`（compact / thread_ts値 / 省略） |
| `source: output` + output.path | `--file` |
| `source: text` + source_text | `--text` |
| `token_env` | `--token-env` |

#### job（同期実行 — `update-job.py` を使用）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | boolean | `false` | 進捗管理の有無 |
| `file` | string | null | ジョブファイルパス（ランナーが自動設定） |
| `id` | string | null | 更新対象のジョブID（ランナーが自動設定） |
| `level` | enum | `info` | `debug`: 全ステップ更新 / `info`: 開始・完了のみ / `error`: エラー時のみ |

## 責務分離

| パラメータ | エージェントに渡す | ランナーが消費 | 理由 |
|---|---|---|---|
| `input.*` | ✅ | ✅ | エージェントが入力ソースを知る必要あり |
| `output.*` | ✅ | ✅ | エージェントが出力先・フォーマットを知る必要あり |
| `log.*` | ❌ | ✅ | ランナーがログファイルにリダイレクト |
| `slack.*` | ❌ | ✅ | ランナーが通知実行 |
| `job.*` | ❌ | ✅ | ランナーがジョブ更新 |

## パラメータ解決の優先順位

1. **明示的パラメータ** — プロンプト冒頭のYAMLブロックに記載された値
2. **agent-common.md のデフォルト値** — 未指定フィールドに適用
3. **IDE対話時の確認フロー** — YAMLブロック不在時にユーザーへ確認

## 呼び出し元別の典型例

### パイプライン経由（自動実行）

```yaml
---
agent_params:
  input:
    source_type: file
    source_path: "Documents/works/scout_reports/tech_trends/daily/2026-05-16_tech_trends.md"
    format_ref: "~/.shared-ai/interfaces/notion-trend-scout-output.md"
  output:
    enabled: true
    path: "Documents/works/research_materials/2026-05-17_deno-2-node-compat.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
---
```

### dispatch-wrapper 経由（半自動）

```yaml
---
agent_params:
  input:
    source_type: theme
    source_theme: "Deno 2.0 の Node.js 互換性"
  output:
    enabled: true
    path: "Documents/works/research_materials/2026-05-17_deno-2-node-compat.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
---
```

### IDE対話（手動）

YAMLブロックなし → agent-common.md §0 の確認フローが発動。

```
ユーザー: Deno 2.0のNode.js互換性について調べて
エージェント: （§0 確認フロー実行）
```
