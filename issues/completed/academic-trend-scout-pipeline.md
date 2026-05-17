# academic-trend-scout パイプライン化

## 変更種別

feat

## 概要

- academic-trend-scoutを単一コンテキスト実行からパイプライン化し、コンテキスト逼迫を解消する
- gws-trend-scout-pipelineと同様のアーキテクチャを採用

## 問題・背景

- 月曜日のarXivフィードが1437件/396KBに膨張し、単一コンテキストでは処理しきれない
- Web検索が全滅し、レポートが12件に縮小する問題が発生（正常時28件）
- フィードの分野別分割 → 各分野を独立したkiro-cliプロセスで処理することで解決

## 設計方針

### パイプライン構造

```
Step 0: 対象日決定 + ディレクトリ準備
Step 1: フィードファイルを分野別に分割（Pythonスクリプト）
Step 2: 各分野をkiro-cliで独立実行（academic-trend-searcher）
Step 3: 統合レポート作成（Pythonスクリプトでマージ）
```

### 分野定義（検索カテゴリに対応）

1. ml_ai: arXiv cs.AI + cs.LG + Hugging Face Papers
2. cv_robotics: arXiv cs.CV + cs.RO
3. se_it: arXiv cs.SE
4. economics: arXiv econ.GN + NBER Working Papers
5. behavioral_biz: Web検索のみ（行動心理学・経済心理学 + ビジネス・経営学）
6. interdisciplinary: Web検索のみ（学際・応用 + IoT・カーモビリティ + ドローン）

### 各分野のsearcher処理

- フィードから該当分野の記事を読み込み（分割済みなので小さい）
- Web検索で補完（各分野2〜3回）
- 中間ファイル（Markdown）を出力

### 統合レポート

- 各分野の中間ファイルをマージ
- 注目論文TOP3を選定
- 応用可能性サマリを生成

## 修正対象

- `scripts/run-academic-trend-scout-pipeline.py`（新規）
- `scripts/split-academic-feeds.py`（新規）
- `scripts/merge-academic-intermediate-files.py`（新規）
- `.shared-ai/prompts/academic-trend-searcher.md`（新規）
- `.kiro/agents/academic-trend-searcher.json`（新規）
- `scripts/run-daily-pipeline.py`（AGENTS変更: academic-trend-scout → run-academic-trend-scout-pipeline.py）
- `scripts/create-daily-jobs.py`（ジョブ定義変更）

## タスク分解

### Task 1: フィード分割スクリプト作成

- **対象ファイル:** `scripts/split-academic-feeds.py`
- **変更内容:** フィードファイルを分野別に分割するスクリプト。各分野のフィードサイズを制限（max_items_per_field）

### Task 2: 中間ファイルマージスクリプト作成

- **対象ファイル:** `scripts/merge-academic-intermediate-files.py`
- **変更内容:** 各分野の中間ファイルを統合レポートにマージ。注目論文選定とサマリ生成はkiro-cliに委譲

### Task 3: academic-trend-searcherエージェント作成

- **対象ファイル:** `.shared-ai/prompts/academic-trend-searcher.md`, `.kiro/agents/academic-trend-searcher.json`
- **変更内容:** 分野別の論文検索・要約を行うsearcherエージェント

### Task 4: パイプラインスクリプト作成

- **対象ファイル:** `scripts/run-academic-trend-scout-pipeline.py`
- **変更内容:** Step 0〜3を順次実行するパイプラインスクリプト

### Task 5: 日次パイプラインへの統合

- **対象ファイル:** `scripts/run-daily-pipeline.py`, `scripts/create-daily-jobs.py`
- **変更内容:** AGENTSリストの変更、ジョブ定義の更新

## 影響範囲

- 日次パイプラインの実行順序
- academic-trend-scoutの出力フォーマット（変更なし）
- ジョブ管理ファイルの構造

## テスト計画

- [ ] `scripts/split-academic-feeds.py` が5/11のフィードを正しく分割できること
- [ ] `scripts/run-academic-trend-scout-pipeline.py` が単体で実行できること
- [ ] 出力レポートのフォーマットが既存と同一であること
