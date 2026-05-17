# エージェント作成ガイド

scoutパイプライン等のエージェントを新規作成・改修する際の設計基準。
既存の `*-trend-scout` / `*-event-scout` / `*-digest-scout` の実装パターンに基づく。

詳細な実装パターンは以下の参照ファイルを参照:
- `agent-prompt-guide.md` — プロンプト設計、コンテキスト節約、2段階実行、テーマ分割、コマンド抽象化
- `agent-pipeline-guide.md` — hook連携、パイプライン組み込み、ヘッドレス実行、低頻度更新データ設計

## 命名規則

### 区切り文字

| 対象 | 規則 | 区切り | 例 |
|------|------|--------|-----|
| エージェント名 | ケバブケース | `-` | `tech-trend-scout` |
| プロンプトファイル名 | ケバブケース | `-` | `tech-trend-scout.md` |
| hookファイル名 | ケバブケース | `-` | `agent-output-review.kiro.hook` |
| スクリプトファイル名 | ケバブケース | `-` | `find-job.py` |
| referencesファイル名 | ケバブケース | `-` | `tech-trend-sources.md` |
| steeringファイル名 | ケバブケース | `-` | `agent-creation-guide.md` |
| 出力ディレクトリ名 | スネークケース | `_` | `tech_trends`, `slack_trends` |
| 出力ファイル名 | `{日付}_{テーマkebab}_{種別}.md` | `_`=構造区切り、`-`=単語区切り | `2026-05-05_aws-bedrock_material.md` |

**理由**:
- 設定・定義ファイル（人が管理）: `-` で統一。Kiroの慣習・URL慣習に準拠
- 出力ディレクトリ（プログラムが参照）: `_` で統一。シェル変数代入・split処理が容易
- 出力ファイル名: `_` で split すれば `[日付, テーマ, 種別]` に構造的にパース可能

### ファイル名の語形規則

| 対象 | 語形 | パターン | 良い例 | 悪い例 |
|------|------|----------|--------|--------|
| エージェント名 | **名詞（役割）** | `{領域}-{機能}-{役割}` | `tech-trend-scout` | `scout-tech-trends` |
| hookファイル名 | **名詞（イベント/動作名）** | `{対象}-{動作名}` | `agent-output-review` | `refresh-reference-data` |
| steeringファイル名 | **名詞（文書種別）** | `{対象}-{種別}` | `dev-env`, `py-standards`, `kiro-arch` | `guide-for-creating-agents` |
| スクリプトファイル名 | **動詞始まり（コマンド）** | `{動詞}-{対象}` | `find-job.py`, `create-weekly-jobs.py` | `task-finder.sh` |
| referencesファイル名 | **名詞（データ種別）** | `{トピック}-{文書種別}` or `{エージェント名}-sources` | `agent-prompt-guide`, `tech-trend-sources.md` | `sources-for-tech-trend.md` |

### 詳細ルール

#### エージェント名: `{領域}-{機能}-{役割}`

役割を表す名詞で終わる。「何者か」が一目で分かる命名。

| 役割語 | 意味 | 例 |
|--------|------|-----|
| `scout` | 情報収集・偵察 | `tech-trend-scout`, `lifestyle-event-scout` |
| `writer` | 文書作成 | （将来の文書作成エージェント用） |
| `planner` | 企画・計画 | `tech-poc-planner` |
| `updater` | データ更新 | `slack-user-directory-updater` |
| `reviewer` | レビュー・検証 | `agent-output-reviewer`, `code-reviewer` |
| `architect` | 設計・構造化 | `spec-architect` |
| `tester` | テスト実行 | `integration-tester` |
| `analyst` | 分析・調査報告 | `github-repo-analyst` |
| `creator` | 成果物生成 | `slide-creator` |

サブエージェント（親エージェントから委譲される）は親名にサフィックスを付ける:
- `slack-trend-scout-channel`（チャンネル別収集）
- `slack-trend-scout-merge`（統合）
- `gws-trend-extractor`（抽出フェーズ）
- `markdown-reporter`（汎用統合レポート作成）

#### hookファイル名: `{対象}-{動作名}`

| パターン | 例 | 説明 |
|----------|-----|------|
| `{対象}-{動作}` | `agent-output-review` | エージェント出力のレビュー |
| `{対象}-{動作}` | `free-notion-mcp-port` | Notion MCPポート解放 |
| `{対象}-{動作}` | `tech-poc-plan` | PoC計画の実行 |
| `{対象}-{検証名}` | `domain-frontmatter-check` | ドメインファイルのfrontmatter検証 |

#### steering ファイル名: `{対象}-{種別}`（コンパクト）

steeringは略語を使い短くする。`-guide`, `-rules`, `-base` 等の冗長なサフィックスは省略。

| パターン | 例 | 説明 |
|----------|-----|------|
| `{対象}-{種別}` | `dev-env`, `py-standards`, `gws-rules` | 本体参照型 |
| `{対象}-{動作}` | `spec-frontmatter`, `spec-completion` | fileMatch型 |
| `{対象}` | `pr-creation`, `design-format` | 種別が自明な場合 |

#### references ファイル名: `{トピック}-{文書種別}`（フルネーム）

referencesは省略せず、内容が明確に分かる名前にする。

| 文書種別 | 意味 | 例 |
|----------|------|-----|
| `-guide` | 手順・ガイド | `agent-creation-guide`, `agent-prompt-guide` |
| `-sources` | 収集対象ソース一覧 | `tech-trend-sources` |

#### スクリプトファイル名: `{動詞}-{対象}`

| 動詞 | 意味 | 例 |
|------|------|-----|
| `find-` | 検索・取得 | `find-job.py` |
| `update-` | 更新 | `update-job.py` |
| `create-` | 生成 | `create-weekly-jobs.py` |
| `fetch-` | 外部取得 | `fetch-rss-feeds.py` |
| `check-` | 検証・判定 | `check-directory-freshness.py` |

## trend / digest の棲み分け（日次収集 vs 週次集約）

scoutパイプラインは「日次で収集 → 週次で集約」の2層構造を基本とする。

### 設計原則

| 層 | 命名パターン | 実行頻度 | 役割 | API呼び出し |
|---|---|---|---|---|
| 日次収集層 | `{source}-trend-scout` | 毎日 | 対象ソースからデータを直接取得し、日次レポートを出力 | 多い（DB全件クエリ、全文検索、Web検索等） |
| 週次集約層 | `{source}-digest-scout` | 週1回 | 日次レポートを読み込み、統合・分析・追加調査を行う | 最小限（追加調査のみ） |

### 責務の分離

```
[trend-scout] ← 重い処理（API大量呼び出し、データ取得）
  出力: daily/{YYYY-MM-DD}_{source}_daily.md
         ↓ ファイルとして蓄積
[digest-scout] ← 軽い処理（ファイル読み込み + 最小限のAPI追加調査）
  入力: daily/ 配下の直近N日分
  出力: weekly/{YYYY-MM-DD}_{source}_weekly_digest.md
```

### digest-scoutの設計ルール

1. **日次レポートを主入力とする。ソースAPIの全件クエリ・全文検索は使用しない**
2. API呼び出しは「追加調査」のみ（期限超過タスクの最新確認、未決スレッドの最新返信等）
3. API呼び出し数の上限を設ける（目安: 最大10〜15件）
4. 日次レポートで既に解決済みの情報（ユーザー名変換等）は再取得しない
5. 欠損日がある場合はスキップし、レポートに明記する
6. 日次レポートが不足している場合のフォールバック動作を定義する
7. **日次レポート間の重複を検知し、重み付けを正規化する**（下記参照）

### digest-scoutの重複正規化ルール

日次収集では日付フィルタの許容幅（±1日）やpublishedDate=nullにより、同一記事が複数日のレポートに含まれることがある。digest集約時にこれを補正する。

**検知基準（以下のいずれかで同一と判定）:**
- 同一URL
- タイトルの類似度が高い（同一ソースかつタイトル先頭20文字が一致）

**正規化ルール:**
- 同一記事が複数日に出現した場合、**最初に出現した日のみをカウント**する
- 重要度・関連度の評価は1回分として扱う（出現回数で重み付けしない）
- digestレポートには初出日を記載する

### 現在の実装

| ソース | 日次（trend） | 週次（digest） | 集約期間 |
|---|---|---|---|
| Slack | `slack-trend-scout` | `slack-digest-scout` | 7日（追跡14日） |
| GWS | `gws-trend-scout` | `gws-digest-scout` | 7日 |
| Notion | `notion-trend-scout` | `notion-digest-scout` | 14日 |

### 新規ソース追加時の判断

1. まず `{source}-trend-scout`（日次収集）を作成し、日次パイプラインに組み込む
2. 日次レポートが十分に蓄積されたら `{source}-digest-scout`（週次集約）を作成
3. digest-scoutは**必ず日次レポートを主入力とする設計**にする（APIを直接叩かない）

## 一時ファイル規約

エージェントが中間データを書き出す一時ファイルは以下のルールに従う。

### 配置先

```
{出力ディレクトリ}/tmp/{ファイル名}
```

例:
- `Documents/works/scout_reports/tech_trends/daily/tmp/raw_results.md`
- `Documents/works/scout_reports/tech_trends/daily/tmp/feeds.md`

### ルール

| 項目 | 規約 |
|------|------|
| ディレクトリ | 各出力先の `tmp/` サブディレクトリ |
| ファイル名 | 日付なし（`raw_results.md`, `feeds.md` 等） |
| 上書き | 実行のたびに上書き（前回の内容は破棄） |
| `raw_results.md` | 処理が成功で完了した場合、最後に削除する |
| `feeds.md` | RSS事前取得結果。次回実行時に上書きされるため残置OK |
| `.gitignore` | `tmp/` ディレクトリは `.gitignore` に含める |

### 禁止事項

- ❌ `.tmp_{日付}_` プレフィックスでの命名（廃止済み）
- ❌ 出力ディレクトリ直下への一時ファイル配置
- ❌ 日付入りの一時ファイル名（蓄積してディスクを圧迫する）

## ファイル構成とエージェント定義

### ファイル構成

```
.shared-ai/prompts/{agent-name}.md     # プロンプト本体（~3〜8KB目標）
.shared-ai/references/{name}-sources.md # 収集対象ソース参照（Web検索系のみ）

.kiro/agents/{agent-name}.json          # エージェント定義（メタデータ・権限）
.kiro/hooks/{hook-name}.kiro.hook       # パイプラインwatcher / 手動トリガー
```

### エージェント定義（JSON）

```json
{
  "name": "{agent-name}",
  "description": "{1〜2文の説明}",
  "prompt": "file://./prompts/{agent-name}.md",
  "tools": ["read", "write", "web"],
  "allowedTools": ["web"],
  "toolsSettings": {
    "write": {
      "allowedPaths": ["Documents/works/scout_reports/{output_dir}/**"]
    }
  },
  "resources": [],
  "includeMcpJson": false,
  "model": "claude-sonnet-4",
  "welcomeMessage": "{起動時メッセージ}"
}
```

### `includeMcpJson` 設定ルール（必須）

全エージェントで `includeMcpJson` を明示的に設定すること（暗黙のデフォルトに頼らない）。

| 設定値 | 条件 |
|--------|------|
| `true` | Slack MCP、Notion MCP、Playwright MCP、DBHub MCPのいずれかを使用する場合 |
| `false` | 上記MCPを使用しない場合（Web検索、shell、ファイル操作のみ） |

**背景:** `true` にすると全MCPサーバー（Notion含む）が一括ロードされ、OAuth認証フローが発生する。MCPを使わないエージェントでは不要な認証画面の表示やリソース消費を避けるため、`false` を明示する。

**判定基準:**
- Web検索（`web` ツール）のみ → `false`
- `gws` CLI（shell経由）のみ → `false`
- `gh` CLI（shell経由）のみ → `false`
- Slack MCPでメッセージ投稿・取得 → `true`
- Notion MCPでページ検索・取得 → `true`
- Playwright MCPでブラウザ操作 → `true`
- DBHub MCPでSQL実行 → `true`

## チェックリスト（新規エージェント作成時）

### エージェント本体

- [ ] `.kiro/agents/{name}.json` 作成（権限・モデル・書き込み先）
- [ ] `.shared-ai/prompts/{name}.md` 作成（8KB以下。構造は `agent-prompt-guide.md` 参照）
- [ ] `.shared-ai/prompts/{name}.md` に `agent-common.md` の該当セクション参照を含める（§1〜§9から選択）
- [ ] `.shared-ai/references/{name}-sources.md` 作成（Web検索系のみ）
- [ ] 出力先ディレクトリの存在確認（`Documents/works/scout_reports/{dir}/`）
- [ ] プロンプトサイズ確認（`wc -c` で8KB以下）

### パイプライン組み込み（詳細は `agent-pipeline-guide.md` 参照）

- [ ] `scripts/create-{frequency}-jobs.py` に子ジョブ追加
- [ ] `scripts/run-{frequency}-pipeline.py` の `AGENTS` 配列に追加
- [ ] `scripts/run-{frequency}-pipeline.py` の `NOTIFY_FILE_MAP` に追加（通知ONは `NotifyEntry(template)`、通知OFFは `NotifyEntry("", enabled=False)`）
- [ ] `scripts/fetch-rss-feeds.py` にカテゴリ追加（RSS必要な場合）
