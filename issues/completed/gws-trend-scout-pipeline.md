# gws-trend-scout-pipeline: パイプライン化設計

## 変更種別

refactor / feat

## 概要

`gws-trend-scout` エージェントの単一コンテキスト実行を廃止し、`run-gws-trend-scout-pipeline.py` による段階的実行方式に移行する。種別ごとにコンテキストを分離し、100件超のメタデータでもコンテキスト圧迫なく処理できるようにする。

## 問題・背景

- **現状**: `gws-trend-scout` が1つのコンテキストで5種別（Docs/Slides/Sheets/Forms/PDF）を順次処理
- **問題1**: 種別ごとのメタデータ取得・フィルタリング・深掘りが同一コンテキストに蓄積し、後半の種別でコンテキストが圧迫される
- **問題2**: 深掘り件数を増やしたい場合（例: top 10）、5種別 × 10件 × 8KB = 400KBがコンテキストに流入し破綻する
- **問題3**: 1種別の失敗が後続種別に影響する（エラーリカバリが困難）
- **解決**: 種別ごとに独立したkiro-cliプロセスで実行し、コンテキストを完全分離

## 新パイプライン構成

```
run-gws-trend-scout-pipeline.py
│
├── Step 0: 対象日決定 + ディレクトリ準備（Python内で完結）
│
├── Step 1: メタデータ一括取得（Python内で完結、kiro-cli不要）
│   ├── gws drive files list → tmp/docs_metadata.ndjson
│   ├── gws drive files list → tmp/slides_metadata.ndjson
│   ├── gws drive files list → tmp/sheets_metadata.ndjson
│   ├── gws drive files list → tmp/forms_metadata.ndjson
│   └── gws drive files list → tmp/pdf_metadata.ndjson
│
├── Step 2: フィルタリング（Python内で完結、kiro-cli不要）
│   ├── filter-gws-drive-metadata.py → tmp/docs_filtered.json
│   ├── filter-gws-drive-metadata.py → tmp/slides_filtered.json
│   ├── filter-gws-drive-metadata.py → tmp/sheets_filtered.json
│   ├── filter-gws-drive-metadata.py → tmp/forms_filtered.json
│   └── filter-gws-drive-metadata.py → tmp/pdf_filtered.json
│
├── Step 3: 種別ごとの深掘り＋中間ファイル作成（kiro-cli × 5、各独立コンテキスト）
│   ├── kiro-cli --agent gws-trend-extractor → tmp/docs.md
│   ├── kiro-cli --agent gws-trend-extractor → tmp/slides.md
│   ├── kiro-cli --agent gws-trend-extractor → tmp/sheets.md
│   ├── kiro-cli --agent gws-trend-extractor → tmp/forms.md
│   └── kiro-cli --agent gws-trend-extractor → tmp/pdf.md
│
├── Step 4: 統合レポート作成（kiro-cli × 1、独立コンテキスト）
│   └── kiro-cli --agent markdown-reporter → {date}_gws_daily.md
│
└── Step 5: 完了（通知はrun-daily-pipeline.pyのStep 4で実施）
```

## 設計ポイント

### Step 1〜2: Pythonで直接実行（kiro-cli不要）

メタデータ取得とフィルタリングはAIの判断が不要な機械的処理。
パイプラインスクリプト内で `subprocess.run` で直接実行する。

```python
# Step 1: メタデータ取得
subprocess.run(["gws", "drive", "files", "list", "--page-all", ...], stdout=open(ndjson_path, "w"))

# Step 2: フィルタリング
subprocess.run(["python3.12", filter_script, "--input", ndjson_path, "--output", filtered_path, ...])
```

**メリット**: kiro-cliのオーバーヘッド（起動時間、コンテキスト消費）がゼロ。

### Step 3: 種別ごとに独立kiro-cli実行

各種別のextractorは独立したコンテキストで動作する。

```python
for type_config in TYPE_CONFIGS:
    prompt = f"""
    gws-trend-extractor として以下の種別を処理してください。
    
    種別: {type_config.name}
    アイコン: {type_config.icon}
    対象期間開始: {base_date}
    対象期間終了: {base_date}
    中間出力ファイル: {type_config.output_path}
    深掘りコマンド: {type_config.drill_command}
    深掘り上位件数: {type_config.top_count}
    フィルタ結果ファイル: {type_config.filtered_path}
    
    フィルタ結果ファイルを readFile で読み込み、関連度判定・カテゴリ分類・深掘り・中間ファイル出力を行ってください。
    """
    run_kiro_cli(prompt, log_file, agent_name="gws-trend-extractor")
```

**メリット**: 
- 各種別が完全に独立したコンテキストで動作（最大100KB/種別）
- 1種別の失敗が他に影響しない
- top 10にしても各コンテキスト内で完結

### Step 4: 統合レポート

中間ファイル5つを読み込んで統合レポートを生成。汎用の `markdown-reporter` エージェントを使用。

```python
prompt = f"""
  入力ファイル: {', '.join(intermediate_files)}
  出力先: Documents/works/scout_histories/gws_trends/daily/{base_date}_gws_daily.md
  フォーマット指示ファイル: ~/.shared-ai/interfaces/gws-trend-report-output.md
  
  対象期間: {base_date}
  
  【重要: コンテキスト節約ルール】
  完了時は以下の形式のみで報告すること。レポート全文やファイル内容は絶対に返さないこと:
  ✅ 統合レポート完了
  - 出力: {{ファイルパス}}
  - ドキュメント総数: {{N}}件
"""
run_kiro_cli(prompt, log_file, agent_name="markdown-reporter")
```

`markdown-reporter` は以下の3パラメータで動作する汎用エージェント:
- **入力ファイル**: 統合対象の中間ファイル群
- **出力先**: 最終レポートのパス
- **フォーマット指示ファイル**: 出力構成・スタイルの定義（interfacesファイル）

gws固有のロジック（注目ドキュメント選定、種別横断の傾向分析等）は `interfaces/gws-trend-report-output.md` に定義済み。
github-repo-analyst等の他パイプラインでも、フォーマット指示ファイルを差し替えるだけで同じエージェントを再利用できる。

### run-daily-pipeline.py との統合

`run-daily-pipeline.py` のエージェントリストから `gws-trend-scout` を削除し、代わりにパイプラインスクリプトを呼び出す:

```python
# run-daily-pipeline.py の pre_agent_hook で gws-trend-scout をスキップ
# 代わりに post_agents_hook でパイプラインスクリプトを実行

# または: AGENTS リストから gws-trend-scout を削除し、
# rss_fetch_hook の後に gws-trend-scout-pipeline を直接実行
```

**推奨**: `AGENTS` リストに `gws-trend-scout` を残しつつ、`pre_agent_hook` でパイプラインスクリプトに委譲する方式。これにより:
- ジョブファイル管理（進捗表示）が既存の仕組みで動く
- 通知（Step 4）も既存の仕組みで動く
- パイプラインスクリプトの成功/失敗が親パイプラインに伝播する

## 種別パラメータ定義

```python
@dataclass
class TypeConfig:
    name: str           # docs / slides / sheets / forms / pdf
    icon: str           # 📄 / 📊 / 📈 / 📝 / 📎
    mime: str           # MIME type
    drill_command: str  # 深掘りコマンドテンプレート
    top_count: int      # 深掘り上位件数
    
TYPE_CONFIGS = [
    TypeConfig("docs", "📄", "application/vnd.google-apps.document",
               "gws docs documents get --params '{\"documentId\": \"{ID}\"}' | python3.12 ~/scripts/extract-gws-doc-text.py", 10),
    TypeConfig("slides", "📊", "application/vnd.google-apps.presentation",
               "gws slides presentations get --params '{\"presentationId\": \"{ID}\"}' | python3.12 ~/scripts/extract-gws-slides-text.py", 10),
    TypeConfig("sheets", "📈", "application/vnd.google-apps.spreadsheet",
               "gws sheets spreadsheets get --params '{\"spreadsheetId\": \"{ID}\"}' | head -c 8000", 10),
    TypeConfig("forms", "📝", "application/vnd.google-apps.form",
               "gws forms forms get --params '{\"formId\": \"{ID}\"}' | head -c 8000", 5),
    TypeConfig("pdf", "📎", "application/pdf", "", 0),
]
```

## コンテキスト消費の比較

| 方式 | Docs | Slides | Sheets | Forms | PDF | 合計 |
|------|------|--------|--------|-------|-----|------|
| **旧方式**（単一コンテキスト、top 3） | 24KB | 24KB | 24KB | 16KB | 0KB | 88KB累積 |
| **新方式**（独立コンテキスト、top 10） | 80KB | 80KB | 80KB | 40KB | 0KB | 各独立 |

新方式では各種別が独立コンテキストなので、累積しない。top 10でも各80KB以内で余裕。

## 修正対象ファイル

### 新規作成

| ファイル | 内容 |
|---|---|
| `scripts/run-gws-trend-scout-pipeline.py` | パイプラインスクリプト |
| `.kiro/agents/gws-trend-extractor.json` | extractor エージェント定義 |
| `.shared-ai/prompts/markdown-reporter.md` | 汎用レポート統合エージェント |
| `.kiro/agents/markdown-reporter.json` | markdown-reporter エージェント定義 |

### 更新

| ファイル | 変更内容 |
|---|---|
| `scripts/run-daily-pipeline.py` | `pre_agent_hook` で gws-trend-scout をパイプラインスクリプトに委譲 |
| `.shared-ai/prompts/gws-trend-extractor.md` | no-interactive対応（フィルタ結果ファイルパスをプロンプトから受け取る） |
| `.shared-ai/prompts/gws-trend-scout.md` | IDE実行時の手順書として残す（パイプライン実行時は不使用） |
| `.shared-ai/interfaces/gws-trend-extractor-output.md` | extractor中間ファイルフォーマット定義 |
| `.shared-ai/interfaces/gws-trend-report-output.md` | 統合レポートの構成指示（markdown-reporter向け） |

### 廃止予定

| ファイル | 理由 |
|---|---|
| `.shared-ai/prompts/gws-trend-scout-aggregator.md` | `markdown-reporter` に置き換え |
| `.kiro/agents/gws-trend-scout-aggregator.json`（存在する場合） | 同上 |

## タスク分解

### Task 1: markdown-reporter エージェント作成

- **対象ファイル:** `.shared-ai/prompts/markdown-reporter.md`, `.kiro/agents/markdown-reporter.json`
- **変更内容:** 汎用レポート統合エージェント。入力ファイル/出力先/フォーマット指示ファイルの3パラメータで動作。no-interactive前提。

### Task 2: gws-trend-extractor エージェント定義

- **対象ファイル:** `.kiro/agents/gws-trend-extractor.json`
- **変更内容:** extractor.mdを参照するagent JSON作成。tools: read/write/shell

### Task 3: extractor.md の no-interactive 対応

- **対象ファイル:** `.shared-ai/prompts/gws-trend-extractor.md`
- **変更内容:** プロンプトからフィルタ結果ファイルパスを受け取り、readFileで読み込む手順を明記

### Task 4: interfaces 分割（extractor-output / report-output）

- **対象ファイル:** `.shared-ai/interfaces/gws-trend-extractor-output.md`, `.shared-ai/interfaces/gws-trend-report-output.md`
- **変更内容:** 旧 `gws-trend-scout-output.md` を分割。extractor向け（中間ファイルフォーマット+記載ルール）とreporter向け（統合レポート構成指示）に分離

### Task 5: パイプラインスクリプト作成

- **対象ファイル:** `scripts/run-gws-trend-scout-pipeline.py`
- **変更内容:** Step 0〜5の実装。_pipeline_common.pyは使用しない（構造が異なるため）

### Task 6: run-daily-pipeline.py との統合

- **対象ファイル:** `scripts/run-daily-pipeline.py`
- **変更内容:** `pre_agent_hook` で gws-trend-scout 実行時にパイプラインスクリプトを呼び出し

### Task 7: gws-trend-scout-aggregator 廃止

- **対象ファイル:** `.shared-ai/prompts/gws-trend-scout-aggregator.md`
- **変更内容:** markdown-reporter への移行完了後に廃止。gws-trend-scout.md のStep 3の参照先も更新。

### Task 8: 動作確認

- 5/8（木曜、205件）のデータでパイプライン実行
- 各種別の中間ファイル確認
- markdown-reporter による統合レポート確認
- run-daily-pipeline.py からの呼び出し確認

## 影響範囲

- `run-daily-pipeline.py`: gws-trend-scout の実行方式が変わるが、外部インターフェース（ジョブファイル、通知ファイルパス）は変更なし
- IDE実行: `gws-trend-scout.md` はそのまま残すため、IDE上で `gws-trend-scout` エージェントを直接実行することも引き続き可能
- 通知: 出力ファイルパス `{date}_gws_daily.md` は変更なし

## テスト計画

- [ ] パイプラインスクリプト単体実行（5/8データ）で全種別の中間ファイルが生成されること
- [ ] 統合レポートが正常に生成されること
- [ ] run-daily-pipeline.py からの呼び出しで正常動作すること
- [ ] 1種別が失敗しても他の種別が正常に処理されること
- [ ] top 10 で各種別のコンテキストが破綻しないこと
