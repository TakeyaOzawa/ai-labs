# extract-agent-common-module: エージェントプロンプト共通部分の agent-common.md 切り出し

## ステータス

**Task 1〜6: 完了** — agent-common.md 作成、28ファイルのプロンプト置き換え、ガイド更新済み。

**未完了タスクは以下の別issueに分離:**
- `issues/agent-params-schema.md` — Task 8, 9, 15（パラメータ体系の導入）
- `issues/pipeline-redesign.md` — Task 10, 11, 12, 13, 14（パイプライン再設計）

**Task 7（動作確認）** は代表的なエージェント実行で確認する。手動で実施のこと。

## 変更種別

refactor

## 概要

- `.shared-ai/prompts/` 配下の各エージェントプロンプトに散在する共通セクション・パターンを `agent-common.md` として切り出す
- 実装改修時の修正漏れ防止と、エージェント間・外部とのやり取りのインターフェース定義を一元化する

## 問題・背景

### 修正漏れリスク

現在44個のエージェントプロンプトが存在し、以下の共通パターンが各ファイルに**コピペで散在**している。共通ロジックの変更時に全ファイルを手動で更新する必要があり、修正漏れが頻発するリスクがある。

### 一貫性の欠如

同じ目的のセクションでも、エージェントごとに微妙に記述が異なる（例: 日付決定の注意書きの文言、dispatch-agent-wrapper判定の条件文等）。

### インターフェース定義の不在

エージェント間の呼び出し規約（完了報告フォーマット、サブエージェント委譲時のプロンプト構造等）が各プロンプトに分散しており、新規エージェント作成時に「何を守るべきか」が不明確。

## 共通パターン分析結果

### 1. 基準日付の決定（出現: 24エージェント）

```markdown
## 基準日付の決定
基準日がプロンプトで指定されている場合はそれを使用。指定がなければ以下で{前日/当日}を取得:
python3.12 ~/scripts/get-jst-date.py {--yesterday}
**AIモデルの推測に頼らず、必ずスクリプトで確定させること。**
```

該当エージェント: tech-trend-scout, biz-car-trend-scout, academic-trend-scout, web-searcher, tech-poc-planner, tech-blog-material-scout, slack-trend-scout, slack-trend-scout-channel, gws-trend-scout, notion-trend-scout, github-repo-analyst, github-org-trend-scout, github-public-trend-scout, github-public-digest-scout, github-org-digest-scout, github-verification-candidate-scout, tech-event-scout, lifestyle-event-scout, gws-digest-scout, slack-digest-scout, notion-digest-scout, tech-poc-runner, tech-blog-writer, rss-source-updater（計24エージェント）

### 2. dispatch-agent-wrapper 判定 + Slack通知（出現: 1エージェント、ただし今後拡大見込み）

```markdown
**⚠️ dispatch-agent-wrapper 経由で起動されている場合はこの Phase をスキップすること。**
プロンプトに `[引き継ぎ事項: このタスクは dispatch-agent-wrapper 経由で起動されています` という文言が含まれている場合、
wrapper が完了後に自動でレポートをスレッドへ投稿するため、エージェント自身による Slack 通知は不要（二重投稿になる）。

直接起動の場合のみ:
python3.12 ~/scripts/notify-slack.py --file {出力ファイルパス}
```

該当エージェント: web-searcher（プロンプト内に明示的に記載）。他のエージェントのSlack通知はパイプラインスクリプト側（`_pipeline_common.py` の `run_slack_notify_async()`）で処理されるため、プロンプト内には記載されていない。ただし、dispatch-agent-wrapper経由で呼び出されるエージェントが増える場合、この判定ロジックの共通化が必要になる。

**→ 改善方針**: プロンプトテキストの文言解析ではなく、エージェント起動パラメータとして明示的に制御する設計に移行する（後述「エージェント起動パラメータ体系」参照）。

### 3. ファイル書き込み戦略参照（出現: 4エージェント）

```markdown
### ファイル書き込み戦略
`readFile: ~/.shared-ai/references/file-write-strategy-guide.md` の手順に従うこと。
```

該当エージェント: web-searcher, tech-poc-planner, markdown-reporter, code-analyst

### 4. 完了報告フォーマット（出現: 7+エージェント）

```markdown
**完了時は以下の形式のみで報告すること。レポート全文やファイル内容は絶対に返さないこと:**
✅ {エージェント名} 完了
- 出力: {ファイルパス}
- {メトリクス}: {値}
```

該当エージェント: markdown-reporter, github-repo-analyst, code-analyst, slack-trend-scout（自身+サブエージェント向け指示）, slack-trend-scout-channel, slack-trend-scout-merge, gws-trend-scout, tech-poc-planner（週次モード）

### 5. スコープ境界（他エージェントとの役割分担）（出現: 8+エージェント）

```markdown
## スコープ
{担当範囲の明示}。{担当外}→{他エージェント名}が担当。
```

**注意**: スコープ境界の内容自体はエージェント固有であり共通化できない。共通化対象は「スコープセクションを設けること」というテンプレート構造のみ。これは既に agent-prompt-guide.md の「共通構造」で定義済みのため、agent-common.md には含めない。

### 6. 自律実行モード判定（出現: 2エージェント）

```markdown
## 自律実行モード
以下のいずれかに該当する場合、自律実行モードとして動作する:
- プロンプト内にテーマ/パスが既に含まれている
- 「実行してください」等の自律実行を示す指示がある
```

該当エージェント: web-searcher, tech-poc-planner

### 7. 重複排除の準備（Phase 0）（出現: 4エージェント）

```markdown
### Phase 0: 重複排除の準備
過去3日分のレポートからURLを抽出し「既出URLリスト」を作成する。
ただし以下は既出リストに含めない: パスが `/` で終わるURL、`/archive/`・`/feed/`・`/news/`・`/blog/`・`/research/` で終わる一覧ページURL。
```

該当エージェント: tech-trend-scout, biz-car-trend-scout, academic-trend-scout, tech-blog-material-scout

### 8. 検索・収集のフィルタリングルール（出現: 4エージェント）

```markdown
**フィルタリングルール:**
- publishedDateが対象日±1日の範囲外 → 除外（null/未提供の場合は通す）
- 既出URLリストに含まれる → 除外
- トップページ（パスが `/` のみ、または上記一覧パターンで終わる）→ 除外
```

### 9. コンテキスト節約ルール（出現: 8+エージェント）

```markdown
**⚠️ 検索は最大{N}回まで。1回検索するごとに即座にファイルへ書き出すこと。**
検索結果をコンテキストに保持し続けない（即座に書き出す）
```

### 10. 信頼度・鮮度基準参照（出現: 3+エージェント）

```markdown
## 信頼度基準 / 鮮度基準
`readFile: ~/.shared-ai/references/source-reliability-guide.md` を参照。
```

### 11. 出力言語指定（出現: 22+エージェント）

```markdown
出力は日本語で行う
```

該当エージェント: ほぼ全エージェント（slack-dispatch-router, investigator等の一部を除く）。行動原則の末尾に記載されるパターン。

### 12. パイプライン参照（出現: 3エージェント — spec系）

```markdown
## パイプライン参照
- `~/.shared-ai/references/spec-pipeline-guide.md`（エージェント切り替えタイミング・引き継ぎ方法）
```

該当エージェント: implementer, code-reviewer, integration-tester（spec系パイプラインのエージェント群）

## 設計方針

### 配置先

`~/.shared-ai/references/agent-common.md`

理由: `shared-ai-directory-guide.md` の判断基準に従い、「複数箇所から参照される設計知識・手順」は `references/` に配置する。

### 参照方法

各エージェントプロンプトから以下の形式で参照:

```markdown
## 共通規約
`readFile: ~/.shared-ai/references/agent-common.md` の該当セクションに従うこと。
```

### agent-common.md の構造案

```markdown
# エージェント共通規約

## 0. agent_params の解析
### YAMLブロック存在時の解析手順
### YAMLブロック不在時（IDE対話）の確認フロー
### デフォルト値

## 1. 基準日付の決定
### パターンA: 前日取得（*-trend-scout系）
### パターンB: 当日取得（web-searcher, tech-poc-planner等）
### 共通注意事項

## 2. 実行モード判定
### 対話モード vs 自律実行モード
### dispatch-agent-wrapper 経由判定とSlack通知スキップ

## 3. ファイル書き込み戦略
（file-write-strategy-guide.md への参照で代替可能か検討）

## 4. 完了報告フォーマット
### 必須フィールド
### エージェント種別ごとのメトリクス例

## 5. Web検索系エージェント共通規約
### 重複排除（Phase 0）
### フィルタリングルール
### コンテキスト節約（即時書き出し）
### 検索回数制限

## 6. サブエージェント委譲規約
### invokeSubAgent 呼び出しフォーマット
### コンテキスト節約ルール（完了報告のみ返す）

## 7. 信頼度・鮮度基準
（source-reliability-guide.md への参照で代替可能か検討）

## 8. 出力言語
デフォルト: 日本語

## 9. パイプライン参照（spec系エージェント向け）
spec-pipeline-guide.md への参照
```

## 修正対象

### 新規作成
- `~/.shared-ai/references/agent-common.md`

### 更新対象（共通部分を参照に置き換え）
- `~/.shared-ai/prompts/web-searcher.md`
- `~/.shared-ai/prompts/tech-trend-scout.md`
- `~/.shared-ai/prompts/biz-car-trend-scout.md`
- `~/.shared-ai/prompts/academic-trend-scout.md`
- `~/.shared-ai/prompts/tech-blog-material-scout.md`
- `~/.shared-ai/prompts/tech-poc-planner.md`
- `~/.shared-ai/prompts/slack-trend-scout.md`
- `~/.shared-ai/prompts/gws-trend-scout.md`
- `~/.shared-ai/prompts/notion-trend-scout.md`
- `~/.shared-ai/prompts/github-repo-analyst.md`
- `~/.shared-ai/prompts/markdown-reporter.md`
- `~/.shared-ai/prompts/slack-trend-scout-channel.md`
- `~/.shared-ai/prompts/slack-trend-scout-merge.md`
- その他、共通パターンを含む全エージェント

### 関連ドキュメント更新
- `~/.shared-ai/references/agent-prompt-guide.md` — 「共通規約は agent-common.md を参照」の記載追加
- `~/.shared-ai/references/agent-creation-guide.md` — 新規エージェント作成チェックリストに agent-common.md 参照を追加
- `~/.shared-ai/references/shared-ai-directory-guide.md` — agent-common.md の位置づけ説明追加（任意）

## タスク分解

### Task 1: 共通パターンの最終確定と agent-common.md 作成

- **対象ファイル:** `~/.shared-ai/references/agent-common.md`（新規）
- **変更内容:** 上記分析結果を基に、共通規約ドキュメントを作成。各セクションは「何を守るべきか」を明確に定義し、エージェント固有のパラメータ（検索回数上限、出力パス等）はプロンプト側で指定する設計とする

### Task 2: Web検索系エージェント（4ファイル）の共通部分置き換え

- **対象ファイル:** tech-trend-scout.md, biz-car-trend-scout.md, academic-trend-scout.md, tech-blog-material-scout.md
- **変更内容:** 日付決定、重複排除、フィルタリングルール、コンテキスト節約ルールを `agent-common.md` 参照に置き換え

### Task 3: オーケストレーター系エージェント（3ファイル）の共通部分置き換え

- **対象ファイル:** slack-trend-scout.md, gws-trend-scout.md, notion-trend-scout.md
- **変更内容:** 日付決定、完了報告フォーマット、サブエージェント委譲規約を参照に置き換え

### Task 4: 深掘り調査系エージェント（3ファイル）の共通部分置き換え

- **対象ファイル:** web-searcher.md, tech-poc-planner.md, github-repo-analyst.md
- **変更内容:** 日付決定、自律実行モード判定、ファイル書き込み戦略を参照に置き換え。web-searcher.md のみ dispatch-wrapper判定+Slack通知スキップ条件も対象

### Task 5: その他のエージェント（残り12+ファイル）の共通部分置き換え

- **対象ファイル:** markdown-reporter.md, slack-trend-scout-merge.md, code-analyst.md, github-org-trend-scout.md, github-public-trend-scout.md, github-public-digest-scout.md, github-org-digest-scout.md, github-verification-candidate-scout.md, slack-trend-scout-channel.md, slack-digest-scout.md, notion-digest-scout.md, gws-digest-scout.md, tech-event-scout.md, lifestyle-event-scout.md, tech-poc-runner.md, tech-blog-writer.md, rss-source-updater.md
- **変更内容:** 各エージェントが該当する共通パターン（主に日付決定、完了報告、コンテキスト節約、出力言語）を `agent-common.md` 参照に置き換え。変更量が少ないファイルが多いため一括で対応

### Task 6: agent-prompt-guide.md / agent-creation-guide.md の更新

- **対象ファイル:** `~/.shared-ai/references/agent-prompt-guide.md`, `~/.shared-ai/references/agent-creation-guide.md`
- **変更内容:** agent-prompt-guide.md の「共通構造」セクションに agent-common.md への参照を追加。agent-creation-guide.md の新規エージェント作成チェックリストに「agent-common.md の該当セクションを参照する記述をプロンプトに含める」を追加

### Task 7: 動作確認

- **変更内容:** 代表的なエージェント（tech-trend-scout, web-searcher, slack-trend-scout）を実行し、agent-common.md 参照後も正常動作することを確認

## 設計上の判断ポイント

### Q1: agent-common.md のサイズ制限

agent-prompt-guide.md によるとプロンプトサイズ目標は3〜8KB。agent-common.md を全エージェントが readFile する場合、コンテキスト消費が増える。

**対策案:**
- A) セクション番号で「該当セクションのみ参照」を指示する（例: `agent-common.md §1, §3, §5 に従うこと`）
- B) agent-common.md 自体を3KB以内に抑え、詳細は既存の references（file-write-strategy-guide.md, source-reliability-guide.md）に委譲する
- C) 共通部分を「必須」と「任意」に分け、必須のみ agent-common.md に含める

**推奨: B案** — agent-common.md は「何を守るべきか」のルール一覧（3KB以内）に留め、「どうやるか」の詳細は既存 references に委譲する。

### Q2: 既存の references との重複

file-write-strategy-guide.md, source-reliability-guide.md は既に存在する。agent-common.md はこれらを「参照せよ」と指示するハブとして機能させ、内容の重複は避ける。

### Q3: エージェント固有パラメータの扱い

検索回数上限（15回 vs 50回）、出力パス、検索カテゴリ等はエージェント固有。agent-common.md では「検索回数上限はプロンプトで指定された値に従う」のように抽象化し、具体値は各プロンプトに残す。

### Q4: 1行ルール（出力言語等）の扱い

「出力は日本語で行う」のような1行ルールは、agent-common.md に集約し各プロンプトからは削除する。

**理由**: 後方互換を設けない方針のため、agent-common.md が必ず読み込まれることが保証される。各プロンプトに残す冗長性は不要。

## 影響範囲

- 全44エージェントプロンプトのうち、少なくとも24ファイルが直接影響を受ける（基準日付パターンのみで24件）
- agent-prompt-guide.md（新規エージェント作成ガイド）
- 既存パイプラインの動作（agent-common.md の readFile が追加されるため、コンテキスト消費が微増）

## リスク・注意点

- **コンテキスト消費増**: 各エージェント実行時に agent-common.md の readFile が追加される。サイズを3KB以内に抑えることで緩和
- **過度な抽象化**: 共通化しすぎるとエージェント固有の挙動が分かりにくくなる。「何を共通化し、何をプロンプトに残すか」の線引きが重要
- **パイプライン再設計の影響範囲**: `_pipeline_common.py` の `PipelineConfig` 変更は全パイプラインスクリプト（daily, weekly, github-org, github-repo-analysis の4ファイル移行 + gws, academic の2ファイル廃止）に波及する。一括移行が必要（段階的移行は中途半端な状態を生む）
- **readFile チェーン**: agent-common.md → file-write-strategy-guide.md のように readFile が連鎖すると、コンテキスト消費が累積する。チェーンは最大2段に抑える
- **YAMLブロック解析の信頼性**: LLMがYAMLを正確に解析する前提。単純なkey-value構造に留め、複雑なネストは避ける
- **launchd plist**: パイプラインスクリプトのインターフェース変更がlaunchd経由の自動実行に影響しないことを確認する必要がある（引数変更がなければ影響なし）
- **移行中のlaunchd停止**: Task 10〜11の実施中は `manage-scheduler.py unload` で自動実行を停止し、移行完了後に `manage-scheduler.py load` で再開すること。中途半端な状態で自動実行が走るとパイプライン全体が停止する

## テスト計画

- [ ] agent-common.md が3KB以内に収まっていること
- [ ] agent-params-schema.md のスキーマが全パラメータを網羅していること
- [ ] `invoke-agent.py` で手動実行時に正しいYAMLブロックが生成されること
- [ ] `run-daily-pipeline.py` が新しい `build_steps()` 方式で全ステップを正常実行できること
- [ ] tech-trend-scout を新パラメータ方式で実行し、output/log/slack が正しく動作すること
- [ ] web-searcher を `slack.enabled: false` で実行し、Slack通知がスキップされること
- [ ] dispatch-agent-wrapper 経由で web-searcher を呼び出し、`slack.enabled: false` が正しく伝播すること
- [ ] launchd経由の自動実行（daily/weekly）が新設計で正常動作すること
- [ ] `agent_params` ブロックなしでエージェントを呼び出した場合（IDE対話時）、ユーザーにinput/output/log/slack/jobの確認が行われること
- [ ] IDE対話時のSlack通知デフォルトが「必要（compact）」で動作すること

## IDE対話時の `agent_params` 不在対応

パイプライン経由・`invoke-agent.py` 経由ではランナーが `agent_params` YAMLブロックを自動生成するが、Kiro IDE内で直接エージェントと対話する場合はランナーが存在しない。

**設計方針: エージェントがユーザーに確認する方式**

`agent-common.md` に以下のルールを追加:

```
## agent_params の解析

1. プロンプト冒頭に `---` + `agent_params:` ブロックが存在する場合 → パラメータを解析して動作
2. ブロックが存在しない場合（IDE対話時）→ ユーザーに以下を確認:
   - input: 入力ソース（ファイルパス / テキスト / なし）
   - output: 出力先パス（デフォルト提案付き）
   - log: ログ出力要否（デフォルト: 不要）
   - slack: Slack通知要否（デフォルト: 必要、thread_mode: compact）
   - job: 進捗管理要否（デフォルト: 不要）
```

**挙動の違い:**

| 起動方式 | `agent_params` | log | slack | job | 確認フロー |
|---|---|---|---|---|---|
| パイプライン経由 | 自動生成（input+output） | ランナーが実行 | ランナーが実行（compact） | ランナーが実行 | 確認なし（自律実行） |
| `invoke-agent.py` | 自動生成（input+output） | ランナーが実行 | ランナーが実行（compact） | デフォルト無効 | 確認なし（CLI引数で制御） |
| IDE対話 | なし | エージェントが確認 | エージェントが確認（デフォルト: 必要、compact） | エージェントが確認 | ユーザーに確認後実行 |

**IDE対話時のエージェント確認例:**

```
ユーザー: 「Deno 2のNode互換性について調べて」

エージェント: 以下の設定で実行します。変更があれば指示してください。
- 入力: テキスト（上記の依頼内容）
- 出力: Documents/works/research_materials/2026-05-17_deno-2-node-compat.md
- ログ: なし
- Slack通知: あり（compact）
- 進捗管理: なし

（確認後、実行開始）
```

**IDE対話時のSlack通知実行:**
エージェントが処理完了後、`notify-slack.py` を直接実行する（ランナー不在のため）:
```bash
python3.12 ~/scripts/notify-slack.py --file {output.path} --thread compact
```

**注意:** この確認フローは対話モードのエージェント（web-searcher, tech-poc-planner等）でのみ発生する。パイプライン専用エージェント（tech-trend-scout等）はIDE対話で直接呼ばれることを想定しない。

### 追加タスク

#### Task 15: agent-common.md に IDE対話時の確認フローを追加

- **対象ファイル:** `~/.shared-ai/references/agent-common.md`
- **変更内容:** `agent_params` 解析セクションに「ブロック不在時の確認フロー」を追加。デフォルト値（slack: 必要/compact、log: 不要、job: 不要）を明記。確認後に `notify-slack.py` を直接実行する手順を記載

## エージェント起動パラメータ体系（agent-common.md の中核設計）

### 背景・動機

現状、エージェントの振る舞い制御（Slack通知の要否、出力先、ログレベル等）はプロンプトテキスト内の文言解析に依存している（例: `[引き継ぎ事項: このタスクは dispatch-agent-wrapper 経由で起動されています`）。これは:
- 脆弱（文言の微妙な変更で判定が壊れる）
- 暗黙的（呼び出し側が何を制御できるか不明確）
- 拡張困難（新しい制御パラメータ追加のたびにプロンプト解析ロジックが増える）

**解決策**: 関数の引数のように、エージェント起動時に構造化されたパラメータを渡す仕組みを定義する。パラメータ未指定フィールドのみ agent-common.md のデフォルト値で補完する。`agent_params` ブロックが存在しない場合（IDE対話時）はユーザーに確認フローを実行する。

### パラメータ解決の優先順位

```
1. 明示的パラメータ（プロンプト冒頭のYAMLブロック）  ← ランナー経由時の唯一の入力源
2. agent-common.md に定義されたデフォルト値（未指定フィールドのみ）
3. YAMLブロック不在時（IDE対話）→ ユーザーに確認フローを実行し、回答からパラメータを構築
```

**後方互換は設けない。** ランナー経由（パイプライン / invoke-agent.py）の呼び出しは必ず `agent_params` ブロック付きで行う。IDE対話時（ブロック不在）はエージェントがユーザーに確認フローを実行する。

### パラメータ渡し方式

プロンプト冒頭に `---` で囲んだYAMLブロックとして渡す。
**エージェントに渡すのは `input` と `output` のみ。** `log`, `slack`, `job` はパイプラインランナーが消費するパラメータであり、エージェントには渡さない。

```yaml
---
agent_params:
  input:
    source_type: file          # file | text | none
    source_path: "Documents/works/scout_reports/tech_trends/daily/2026-05-16_tech_trends.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
  output:
    enabled: true              # ファイル書き出し要否（デフォルト: true）
    path: "Documents/works/research_materials/2026-05-17_deno-2-node-compat.md"
    format_ref: "~/.shared-ai/interfaces/web-searcher-output.md"
---
「Deno 2のNode互換性について調べて」
```

**責務分離:**

| パラメータ | エージェントに渡す（YAMLブロック） | ランナーが消費（StepParams） | 理由 |
|---|---|---|---|
| `input.*` | ✅ | ✅ | エージェントが入力ソースを知る必要あり |
| `output.*` | ✅ | ✅ | エージェントが出力先・フォーマットを知る必要あり |
| `log.*` | ❌ | ✅ | ランナーがログファイルにリダイレクト。エージェントは関与しない |
| `slack.*` | ❌ | ✅ | ランナーが通知実行。エージェントは関与しない |
| `job.*` | ❌ | ✅ | ランナーがジョブ更新。エージェントは関与しない |

### パラメータスキーマ定義

#### input（必須）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `source_type` | enum | `text` | `file`: ファイルパスから読み込み / `text`: プロンプトテキストから抽出 / `none`: 入力なし |
| `source_path` | string | null | `source_type: file` 時のファイルパス |
| `format_ref` | string | null | 入力フォーマット定義（`~/.shared-ai/interfaces/` 配下） |
| `text` | string | null | `source_type: text` 時の入力テキスト（省略時はプロンプト本文から抽出） |

#### output

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `true` | ファイル書き出し要否 |
| `path` | string | `${HOME}/Documents/works/{agent_category}/{YYYYMMDD}_{summary\|agent_name}.md` | 出力先パス |
| `format_ref` | string | null | 出力フォーマット定義（`~/.shared-ai/interfaces/` 配下） |

`path` のデフォルト値テンプレート:
- `{agent_category}`: エージェント名から推定（例: `web-searcher` → `research_materials`、`tech-trend-scout` → `scout_reports/tech_trends/daily`）
- `{YYYYMMDD}`: 基準日付
- `{summary}`: 依頼内容の要約（kebab-case、最大30文字）
- `{agent_name}`: フォールバック

#### log（Static Dispatch — 同期実行）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `true` | ログ出力要否 |
| `path` | string | `${HOME}/logs/{agent_name}/{YYYYMMDD}_{summary\|agent_name}.log` | ログファイルパス |
| `level` | enum | `info` | `debug` / `info` / `error` |

実装: `scripts/logger.py` の `PipelineLogger` または `get_logger()` を使用。エージェント実行中に同期的にログを書き出す。

#### slack（Dynamic Dispatch — 別プロセスで非同期実行）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `true` | Slack通知要否 |
| `channel` | string | `${SLACK_DISPATCH_DM_CHANNEL}` | 通知先チャンネルID |
| `thread_mode` | enum | `"compact"` | `"compact"`: H1を親メッセージ+残りスレッド / `"sequential"`: 分割順次投稿 / `null`: thread_ts指定時は既存スレッドへ返信 |
| `thread_ts` | string | null | 既存スレッドに返信する場合のタイムスタンプ（指定時は thread_mode を無視） |
| `source` | enum | `"output"` | `"output"`: step.params.output.path のファイルを通知 / `"text"`: source_text を通知 |
| `source_text` | string | null | `source: "text"` 時の通知テキスト |
| `token_env` | string | `"MY_SLACK_OAUTH_TOKEN"` | Slack Bot Tokenの環境変数名 |
| `level` | enum | `info` | `debug`: 全ステップ通知 / `info`: 完了時のみ / `error`: エラー時のみ |

実装: `scripts/notify-slack.py` を `subprocess.Popen` で非同期実行（fire-and-forget）。

**notify-slack.py CLI引数との対応:**

| SlackParams フィールド | notify-slack.py 引数 |
|---|---|
| `channel` | `--channel` |
| `thread_mode` / `thread_ts` | `--thread`（compact / thread_ts値 / 省略） |
| `source: "output"` + `output.path` | `--file` |
| `source: "text"` + `source_text` | `--text` |
| `token_env` | `--token-env` |

#### job（Dynamic Dispatch — 同期実行）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `false` | 進捗管理要否 |
| `file` | string | null | ジョブファイルパス（パイプラインランナーが自動設定） |
| `id` | string | null | 更新対象のジョブID（パイプラインランナーが自動設定） |
| `level` | enum | `info` | `debug`: 全ステップ更新 / `info`: 開始・完了のみ / `error`: エラー時のみ |

実装: `scripts/update-job.py` を使用。パイプラインランナーが `generate_job_file` で生成したジョブファイルのパスとIDを自動注入する。手動実行時はデフォルトで無効。

### dispatch-agent-wrapper との関係

`dispatch-agent-wrapper` のプロンプト文言解析は廃止。ランナー側の `StepParams` で明示的に制御する:

```python
# dispatch-agent-wrapper 経由でエージェントを呼び出す場合の StepParams
Step(
    name="web-searcher",
    executor=AgentExecutor(agent_name="web-searcher", prompt_text="..."),
    params=StepParams(
        input=InputParams(source_type="text"),
        output=OutputParams(enabled=True, path="..."),
        slack=SlackParams(enabled=False),   # wrapper側が通知するため、ステップ単位の通知は無効
        job=JobParams(enabled=True),        # wrapper がジョブ管理を行う
    ),
)
```

エージェントに渡す `agent_params` YAMLブロックには `input` と `output` のみ含まれる。Slack通知の有無はエージェントの知る必要がない情報であり、ランナーが `StepParams.slack.enabled: false` を見て通知をスキップする。

### パイプラインスクリプトの再設計

現状の `_pipeline_common.py` は `NOTIFY_FILE_MAP` / `build_prompt()` / `resolve_notify_path` 等で通知・出力を制御しているが、これらを統一的な「ステップ」概念に再設計する。

#### 設計思想: 統一ステップモデル

パイプラインは**ステップのツリー**として定義する。各ステップは「何を実行するか」の種別に関わらず、同じインターフェースで定義・実行される。ステップは再帰的にネスト可能で、既存のジョブツリー構造（parent → child → grandchild）と1対1で対応する。

```
Pipeline (= root Step)
├── Step (= child job)
├── Step (= child job, with nested steps)
│   ├── Step (= grandchild job)
│   ├── Step (= grandchild job)
│   └── Step (= grandchild job)
└── Step (= child job)
```

**ジョブツリーとの対応:**
- `Pipeline` 全体 = parent job
- `build_steps()` が返すトップレベル `Step` リスト = child jobs
- `Step.steps`（ネストされたステップ） = grandchild jobs
- ジョブファイルは `build_steps()` の結果から**自動生成**する（手動で `create-jobs.py` に渡すJSON定義は廃止）

各ステップは以下の共通属性を持つ:
- **何を実行するか**（executor type）
- **どう実行するか**（同期/非同期、タイムアウト、リトライ）
- **入出力パラメータ**（input, output, log, slack, job）
- **依存関係**（depends_on）
- **子ステップ**（steps — 再帰的ネスト）

#### Step 定義スキーマ

```python
@dataclass
class Step:
    """パイプラインの1実行単位（再帰的にネスト可能）"""
    name: str                          # ステップ名（= ジョブ名）
    executor: Executor                 # 実行方式の定義

    # 実行制御
    mode: str = "sync"                 # "sync" | "async"（非同期は fire-and-forget）
    timeout: int = 300                 # タイムアウト秒（0=無制限）
    retry: RetryPolicy | None = None   # リトライポリシー
    depends_on: list[str] | None = None  # 依存先ステップ名リスト（同一階層内）

    # 入出力パラメータ（全executor共通）
    params: StepParams | None = None   # input, output, log, slack, job

    # ネスト（サブパイプライン相当）
    steps: list["Step"] | None = None  # 子ステップ（grandchild相当）

@dataclass
class RetryPolicy:
    max_attempts: int = 1              # 最大試行回数（1=リトライなし）
    delay: int = 30                    # リトライ間隔（秒）
    backoff: str = "fixed"             # "fixed" | "exponential"

@dataclass
class StepParams:
    """全executor共通のパラメータ"""
    input: InputParams | None = None
    output: OutputParams | None = None
    log: LogParams | None = None
    slack: SlackParams | None = None
    job: JobParams | None = None
```

#### Executor 種別

```python
@dataclass
class Executor:
    """実行方式の基底"""
    type: str                          # "agent" | "script" | "composite" | ...（拡張可能）

@dataclass
class AgentExecutor(Executor):
    """AI CLIエージェント実行（ai-cli-utils.py でコマンド構築 → run_ai_command() で実行）"""
    type: str = "agent"
    agent_name: str = ""               # .kiro/agents/{name}.json のエージェント名
    prompt_text: str = ""              # エージェントに渡すテキスト指示

@dataclass
class ScriptExecutor(Executor):
    """Python/シェルスクリプト実行"""
    type: str = "script"
    command: str = ""                  # 実行コマンド（例: "python3.12 ~/scripts/fetch-rss-feeds.py --category tech"）
    env: dict[str, str] | None = None  # 追加環境変数

@dataclass
class CompositeExecutor(Executor):
    """子ステップを順次実行する複合ステップ（サブパイプライン相当）"""
    type: str = "composite"
    # 子ステップは Step.steps フィールドで定義
    # CompositeExecutor 自体は「子ステップを持つ」ことを示すマーカー
```

#### ジョブツリーとの対応関係

| ジョブツリー（現状） | Step モデル（新設計） |
|---|---|
| parent job | `PipelineConfig` 全体（`name`, `timeout` 等） |
| parent.status | 全 child Step の完了状態から自動導出 |
| child job | `build_steps()` が返すトップレベル `Step` |
| child.job_name | `Step.name` |
| child.timeout | `Step.timeout` |
| child.retry_delay | `Step.retry.delay` |
| child.depends_on | `Step.depends_on` |
| child.child_jobs | `Step.steps`（executor=CompositeExecutor 時） |
| grandchild job | `Step.steps` 内の `Step` |
| grandchild.job_name | ネストされた `Step.name` |
| grandchild.timeout | ネストされた `Step.timeout` |

#### ジョブファイル自動生成

`create-jobs.py` に手動でJSON定義を渡す方式を廃止し、`build_steps()` の結果からジョブファイルを自動生成する:

```python
def generate_job_file(pipeline_name: str, base_date: str, steps: list[Step]) -> Path:
    """Step リストからジョブファイルを生成"""
    parent_job = {
        "job_id": generate_id(),
        "job_name": pipeline_name,
        "status": "running",
        "timeout": sum(s.timeout for s in steps),
        "child_jobs": [step_to_job(s) for s in steps],
    }
    # ... ファイル書き出し

def step_to_job(step: Step) -> dict:
    """Step → ジョブ定義の変換（再帰的）"""
    job = {
        "job_id": generate_id(),
        "job_name": step.name,
        "status": "pending" if step.depends_on else "starting",
        "timeout": step.timeout,
        "retry_delay": step.retry.delay if step.retry else 30,
        "depends_on": step.depends_on,
    }
    if step.steps:
        job["child_jobs"] = [step_to_job(s) for s in step.steps]
    return job
```

これにより:
- `create-daily-jobs.py` / `create-weekly-jobs.py` は廃止
- ジョブ定義とパイプライン定義の二重管理が解消
- `Step` の `timeout` / `retry` / `depends_on` がジョブファイルに自動反映

#### 現状 → 新設計の対応

| 現状 | 新設計 |
|------|--------|
| `AGENTS` リスト（文字列配列） | `build_steps()` が `list[Step]` を返す |
| `NOTIFY_FILE_MAP[agent] = NotifyEntry(...)` | `step.params.slack` |
| `build_prompt(agent, base_date) -> str` | `AgentExecutor.prompt_text` |
| `resolve_notify_path(agent, base_date) -> Path` | `step.params.output.path` |
| `WEEKLY_PIPELINE_MODE_AGENTS` | `AgentExecutor.prompt_text` 内でモード指定 |
| `pre_pipeline_hook` / `rss_fetch_hook` | `ScriptExecutor` ステップとして定義 |
| `pre_agent_hook`（スキップ/委譲判定） | `depends_on` + `build_steps` 内の条件分岐 |
| `post_agents_hook` / `post_notify_hook` | `ScriptExecutor` ステップとして定義 |
| `create-daily-jobs.py` + JSON定義 | `generate_job_file(steps)` で自動生成 |
| サブパイプライン（`.py` エントリ） | `CompositeExecutor` + `Step.steps` |
| ジョブ定義の `timeout` | `Step.timeout` |
| ジョブ定義の `retry_delay` | `Step.retry.delay` |
| ジョブ定義の `depends_on` | `Step.depends_on` |
| ジョブ定義の `child_jobs` | `Step.steps` |

#### 新しい `PipelineConfig` 設計案

```python
@dataclass
class PipelineConfig:
    name: str                          # パイプライン名（= parent job name）
    build_steps: Callable[[str, PipelineContext], list[Step]]  # (base_date, ctx) -> ステップツリー
    default_base_date: Callable[[], str]      # 基準日デフォルト計算
```

```python
@dataclass
class PipelineContext:
    """run_pipeline() が構築し、build_steps に渡すランタイム情報"""
    base_date: str
    log_dir: Path                      # ログ出力ディレクトリ（${HOME}/logs/jobs/{name}/）
    use_job_file: bool                 # --no-job-file で無効化可能
    slack_channel: str = ""            # --slack-channel（ディスパッチャー経由時）
    slack_thread_ts: str = ""          # --slack-thread-ts（ディスパッチャー経由時）
```

**最小化のポイント:**
- `PipelineConfig` は `name` + `build_steps` + `default_base_date` の3フィールドのみ
- `log_dir`, `parent_timeout`, `slack_channel`, `slack_thread_ts` 等のランタイム情報は `PipelineContext` に集約
- `PipelineContext` は `run_pipeline()` がCLI引数から構築し、`build_steps` に渡す
- `build_steps` 内で各ステップの `StepParams` にコンテキスト情報を反映できる（例: ディスパッチャー経由時は全ステップの `slack.thread_ts` を設定）
- `create_jobs_script` は廃止（`build_steps` から自動生成）
- 全hookコールバックは廃止（`ScriptExecutor` ステップとして表現）

#### `run_pipeline()` の新しい実行フロー

```
1. オプション解析（基準日、--no-job-file, --slack-channel, --slack-thread-ts）
2. PipelineContext 構築（CLI引数 + デフォルト値）
3. 環境準備（caffeinate, load_env, SLACK_BOT_TOKEN切り替え）
4. steps = config.build_steps(base_date, context) でステップツリーを生成
   - build_steps 内で context.slack_channel / context.slack_thread_ts を各ステップの
     SlackParams に反映可能（ディスパッチャー経由時の通知先設定）
5. job_file = generate_job_file(config.name, base_date, steps) でジョブファイル自動生成
6. ディスパッチャー経由の場合: 元スレッドへ開始通知（context.slack_channel + context.slack_thread_ts）
7. execute_steps(steps, ExecutionContext(...)) でステップツリーを再帰的に実行:
   a. 各ステップについて:
      - depends_on チェック（依存先が全て completed か）
      - step.params.job.enabled なら ジョブステータスを "running" に更新
      - executor.type に応じた実行:
        * "agent": step.params をYAMLブロック化 → ai-cli-utils.py でコマンド構築 → run_ai_command() で実行
        * "script": subprocess.run(command, timeout=step.timeout)
        * "composite": execute_steps(step.steps, child_context) を再帰呼び出し
      - mode="async" の場合は Popen で起動し次のステップへ
      - タイムアウト判定
      - 失敗時: step.retry に従いリトライ or "failed" に更新
      - 成功時: "completed" に更新
      - step.params.slack.enabled なら通知実行（notify-slack.py 非同期起動）
      - step.params.log.enabled ならログ出力
8. 親ジョブ完了処理（全childの状態から自動判定）
9. ディスパッチャー経由の場合: 元スレッドへ完了通知
10. 完了サマリー + caffeinate解除
```

#### `execute_steps()` の再帰実行とネスト対応

```python
@dataclass
class ExecutionContext:
    """ステップ実行時の共有コンテキスト"""
    job_file: Path | None              # ジョブファイルパス
    use_job_file: bool                 # ジョブ管理有効フラグ
    base_date: str                     # 基準日
    plogger: PipelineLogger            # ロガー
    completed_names: set[str]          # 完了済みステップ名（同一階層内）
    slack_channel: str = ""            # ディスパッチャー経由時の通知先
    slack_thread_ts: str = ""          # ディスパッチャー経由時のスレッドTS

def execute_steps(steps: list[Step], context: ExecutionContext) -> tuple[int, int, int]:
    """ステップリストを順次実行する（再帰対応）。

    CompositeExecutor のステップに遭遇した場合、step.steps を
    新しい ExecutionContext（completed_names をリセット）で再帰呼び出しする。
    これにより、ネストされたステップ内の depends_on は同一階層内で解決される。

    Returns:
        (success_count, failed_count, skipped_count)
    """
    ...
```

**ネスト実行のポイント:**
- `depends_on` は**同一階層内**のステップ名を参照する（親階層のステップは参照不可）
- `CompositeExecutor` ステップの成功/失敗は、子ステップの全完了/一部失敗で判定
- 子ステップのジョブ更新は、ジョブファイル内の対応する `child_jobs` ノードに対して行う
- `ExecutionContext` を再帰的に渡すことで、ログ・ジョブファイル・通知設定を共有

#### _pipeline_common.py のパラメータ体系

`_pipeline_common.py` が扱うパラメータは2層に分かれる:

| 層 | パラメータ | 定義場所 | 用途 |
|---|---|---|---|
| **パイプライン層** | `name`, `base_date`, `log_dir`, `use_job_file`, `slack_channel`, `slack_thread_ts` | `PipelineConfig`（静的） + `PipelineContext`（ランタイム） | パイプライン全体の制御。`build_steps` に渡され、各ステップの `StepParams` に反映される |
| **ステップ層** | `input`, `output`, `log`, `slack`, `job`, `timeout`, `retry`, `mode`, `depends_on` | `Step` dataclass | 個々のステップの制御。パイプラインランナーが直接消費 + エージェントにYAMLブロックとして渡す |

**パイプライン層** → ステップ層への反映例:

```python
def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    # ディスパッチャー経由時: 全ステップの slack に thread_ts を設定
    slack_defaults = SlackParams(
        enabled=True,
        channel=ctx.slack_channel or "${SLACK_DISPATCH_DM_CHANNEL}",
        thread_ts=ctx.slack_thread_ts or None,
        thread_mode="compact" if not ctx.slack_thread_ts else None,
    )

    return [
        Step(
            name="tech-trend-scout",
            ...,
            params=StepParams(
                ...,
                slack=slack_defaults,
                log=LogParams(enabled=True, path=str(ctx.log_dir / "tech-trend-scout.log")),
                job=JobParams(enabled=ctx.use_job_file),
            ),
        ),
        ...
    ]
```

**agent-common.md との関係:**
- `agent-common.md` はエージェント（LLM）が解釈するパラメータ仕様を定義（YAMLブロックの解析ルール）
- `_pipeline_common.py` はパイプラインランナー（Python）がステップを実行する際のパラメータ仕様を定義
- 両者は `StepParams`（input/output/log/slack/job）を共有する:
  - パイプラインランナーが `StepParams` → YAMLブロックに変換してエージェントに渡す
  - エージェントは `agent-common.md` のルールに従いYAMLブロックを解析して動作する
  - パイプラインランナーも `StepParams` を直接消費する（slack通知実行、ジョブ更新、ログ出力）
- `PipelineContext` のパラメータはエージェントには渡さない（ランナー内部で消費し、`build_steps` 内で `StepParams` に変換される）

#### パイプライン定義の具体例（daily）

```python
def build_steps(base_date: str, ctx: PipelineContext) -> list[Step]:
    return [
        # RSS事前取得（旧 rss_fetch_hook）
        Step(
            name="rss-fetch",
            executor=ScriptExecutor(
                command=f"python3.12 ~/scripts/fetch-rss-feeds.py --category tech --date {base_date} --output ..."
            ),
            timeout=120,
            retry=RetryPolicy(max_attempts=2, delay=10),
            params=StepParams(
                log=LogParams(enabled=True, path=str(ctx.log_dir / "rss-fetch.log"), level="info"),
            ),
        ),
        # 技術トレンド収集
        Step(
            name="tech-trend-scout",
            executor=AgentExecutor(
                agent_name="tech-trend-scout",
                prompt_text=f"基準日は {base_date} です。",
            ),
            timeout=300,
            retry=RetryPolicy(max_attempts=2, delay=30),
            depends_on=["rss-fetch"],
            params=StepParams(
                input=InputParams(source_type="none"),
                output=OutputParams(
                    enabled=True,
                    path=f"Documents/works/scout_reports/tech_trends/daily/{base_date}_tech_trends.md",
                    format_ref="~/.shared-ai/interfaces/tech-trend-scout-output.md",
                ),
                log=LogParams(enabled=True, path=str(ctx.log_dir / "tech-trend-scout.log"), level="info"),
                slack=SlackParams(
                    enabled=True,
                    channel=ctx.slack_channel or "${SLACK_DISPATCH_DM_CHANNEL}",
                    thread_ts=ctx.slack_thread_ts or None,
                    thread_mode="compact",
                    level="info",
                ),
                job=JobParams(enabled=ctx.use_job_file),
            ),
        ),
        # GWSトレンド（CompositeExecutor + nested steps = 旧サブパイプライン）
        Step(
            name="gws-trend-scout-pipeline",
            executor=CompositeExecutor(),
            timeout=900,
            depends_on=["rss-fetch"],
            params=StepParams(
                slack=SlackParams(enabled=True, thread_mode="compact", level="info"),
                job=JobParams(enabled=ctx.use_job_file),
            ),
            steps=[
                Step(
                    name="gws-extractor-docs",
                    executor=AgentExecutor(
                        agent_name="gws-trend-extractor",
                        prompt_text=f"基準日は {base_date} です。種別: Docs",
                    ),
                    timeout=300,
                    params=StepParams(
                        output=OutputParams(enabled=True, path="Documents/works/scout_reports/gws_trends/daily/tmp/docs.md"),
                        log=LogParams(enabled=True, level="info"),
                        job=JobParams(enabled=True),
                    ),
                ),
                Step(
                    name="gws-extractor-slides",
                    executor=AgentExecutor(
                        agent_name="gws-trend-extractor",
                        prompt_text=f"基準日は {base_date} です。種別: Slides",
                    ),
                    timeout=300,
                    depends_on=["gws-extractor-docs"],
                    params=StepParams(
                        output=OutputParams(enabled=True, path="Documents/works/scout_reports/gws_trends/daily/tmp/slides.md"),
                        log=LogParams(enabled=True, level="info"),
                        job=JobParams(enabled=True),
                    ),
                ),
                Step(
                    name="gws-markdown-reporter",
                    executor=AgentExecutor(
                        agent_name="markdown-reporter",
                        prompt_text=f"基準日は {base_date} です。中間ファイルを統合してください。",
                    ),
                    timeout=300,
                    depends_on=["gws-extractor-docs", "gws-extractor-slides"],
                    params=StepParams(
                        output=OutputParams(enabled=True, path=f"Documents/works/scout_reports/gws_trends/daily/{base_date}_gws_daily.md"),
                        log=LogParams(enabled=True, level="info"),
                        job=JobParams(enabled=True),
                    ),
                ),
            ],
        ),
        # 鮮度チェック（非同期、結果を待たない）
        Step(
            name="freshness-check",
            executor=ScriptExecutor(
                command="python3.12 ~/scripts/check-directory-freshness.py --type slack --max-age-days 7"
            ),
            mode="async",
            timeout=60,
            depends_on=["tech-trend-scout", "gws-trend-scout-pipeline"],
            params=StepParams(
                log=LogParams(enabled=True, level="debug"),
            ),
        ),
    ]
```

#### 廃止対象

| 廃止 | 理由 |
|------|------|
| `NOTIFY_FILE_MAP` | `step.params.slack` に統合 |
| `resolve_notify_path` コールバック | `step.params.output.path` に統合 |
| `WEEKLY_PIPELINE_MODE_AGENTS` set | `build_steps` 内でプロンプト構築時に判定 |
| `AGENTS` リスト（文字列配列） | `build_steps` が `Step` ツリーを返す |
| `pre_pipeline_hook` / `post_pipeline_hook` | `ScriptExecutor` ステップとして定義 |
| `rss_fetch_hook` | `ScriptExecutor` ステップとして定義 |
| `pre_agent_hook` | `depends_on` + `build_steps` 内の条件分岐で代替 |
| `build_prompt` コールバック | `AgentExecutor.prompt_text` に統合 |
| `create-daily-jobs.py` / `create-weekly-jobs.py` | `generate_job_file(steps)` で自動生成 |
| `create-jobs.py` の `--jobs` / `--jobs-file` | `build_steps` が唯一の定義源 |
| `SubPipelineExecutor` | `CompositeExecutor` + `Step.steps` で表現 |
| `run-gws-trend-scout-pipeline.py`, `run-academic-trend-scout-pipeline.py` | 親パイプラインの `build_steps` 内に `CompositeExecutor` + `Step.steps` として統合 |
| dispatch-agent-wrapper の文言解析 | `step.params.slack.enabled: false` で制御 |

### 手動実行時のパラメータ指定

手動（対話的）実行時は、呼び出し側がパラメータを組み立てる:

```bash
# パイプライン経由（自動生成）
python3.12 ~/scripts/run-daily-pipeline.py

# 手動実行（テンプレートから生成）
python3.12 ~/scripts/invoke-agent.py --agent web-searcher \
  --input-type text --input-text "Deno 2のNode互換性について調べて" \
  --output-path "Documents/works/research_materials/2026-05-17_deno-2-node-compat.md" \
  --slack-enabled true \
  --log-level info
```

`invoke-agent.py`（新規）は内部的に `Step` を1つ構築し、同じ実行ロジックで処理する。

### インターフェース定義ファイル

`~/.shared-ai/interfaces/agent-params-schema.md` として以下を定義:
- `Step` / `Executor` / `StepParams` の完全なスキーマ（型、デフォルト値、説明）
- 各エージェントカテゴリごとのデフォルト値テーブル
- パラメータ解決の優先順位ルール
- 呼び出し側（パイプライン、dispatch-wrapper、手動）ごとの典型的なステップ定義例

### 追加タスク

上記設計に基づき、以下のタスクを追加:

#### Task 8: agent-params-schema.md の作成

- **対象ファイル:** `~/.shared-ai/interfaces/agent-params-schema.md`（新規）
- **変更内容:** エージェント起動パラメータの完全なスキーマ定義。input/output/log/slack/job の全フィールド、デフォルト値、型制約を記載

#### Task 9: agent-common.md へのパラメータ解決ロジック追加

- **対象ファイル:** `~/.shared-ai/references/agent-common.md`
- **変更内容:** 「パラメータ解決」セクションを追加。プロンプト冒頭のYAMLブロック解析手順、デフォルト値適用ルール、`agent_params` ブロック未検出時のエラー処理を記載

#### Task 10: _pipeline_common.py の再設計

- **対象ファイル:** `~/scripts/_pipeline_common.py`, `~/scripts/ai-cli-utils.py`
- **変更内容:**
  - `Step` / `Executor`（AgentExecutor, ScriptExecutor, CompositeExecutor）/ `StepParams` / `RetryPolicy` dataclass を追加
  - `PipelineConfig` を新設計に変更（`name` + `build_steps` + `default_base_date` の3フィールド）
  - `run_pipeline()` を再帰的ステップ実行に変更（`execute_steps()` の再帰呼び出し）
  - `generate_job_file(steps)` を実装（Step ツリー → ジョブファイル自動生成）
  - `NOTIFY_FILE_MAP` / `resolve_notify_path` / `WEEKLY_PIPELINE_MODE_AGENTS` / 全hookコールバック / `build_prompt` を廃止
  - 同期/非同期実行、タイムアウト、リトライの共通ロジックを実装
  - `ai-cli-utils.py` の `build_ai_command()` を拡張: `StepParams` からYAMLブロックを生成しプロンプト冒頭に埋め込む機能を追加（`build_ai_command_with_params(prompt, params, ...)` または既存関数のprompt前処理として実装）

#### Task 11: 各パイプラインスクリプトの移行

- **対象ファイル:** `run-daily-pipeline.py`, `run-weekly-pipeline.py`, `run-github-org-trend-scout-pipeline.py`, `run-github-repo-analysis-pipeline.py`
- **変更内容:**
  - `AGENTS` + `NOTIFY_FILE_MAP` + `build_prompt()` + hook関数群を `build_steps()` に統合
  - RSS取得・鮮度チェック等の既存hookは `ScriptExecutor` ステップとして定義
  - 各エージェントは `AgentExecutor` ステップとして定義（全パラメータ明示）
  - daily/weeklyの旧サブパイプライン（`run-gws-trend-scout-pipeline.py`, `run-academic-trend-scout-pipeline.py`）の内容を `CompositeExecutor` + `Step.steps` として親パイプラインにインライン化し、スクリプト自体は廃止
  - `run-github-org-trend-scout-pipeline.py` は独立パイプライン（独自launchd plist）のため廃止せず、新しい `PipelineConfig` + `build_steps` 方式に移行
  - `create-daily-jobs.py`, `create-weekly-jobs.py` は廃止（`generate_job_file` で自動生成）

#### Task 12: invoke-agent.py の新規作成

- **対象ファイル:** `~/scripts/invoke-agent.py`（新規）
- **変更内容:** 手動実行用のCLIラッパー。コマンドライン引数から `Step` を1つ構築し、`run_pipeline()` と同じ実行ロジックで処理する。パイプラインと手動実行で実行パスが統一される

#### Task 13: dispatch-agent-wrapper.py の移行

- **対象ファイル:** `~/scripts/dispatch-agent-wrapper.py`
- **変更内容:** エージェント呼び出し時に `Step` + `StepParams` を構築する方式に移行。プロンプト内の `[引き継ぎ事項:` 文言埋め込みを廃止し、`StepParams.slack.enabled: false` で通知スキップを制御

#### Task 14: 全エージェントプロンプトから文言解析ロジックを削除

- **対象ファイル:** `web-searcher.md`（現時点で唯一の該当）
- **変更内容:** `dispatch-agent-wrapper` 判定セクションを削除。`agent_params` の解析手順（agent-common.md 参照）に置き換え
