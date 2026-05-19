# github-repo-analyst 出力フォーマット

GitHub APIを使用したリポジトリ調査の出力フォーマット。
パイプラインスクリプトが `## 機械可読データ` セクションのYAMLブロックを自動抽出し、後続エージェントへの入力として使用する。

## フロントマター

```yaml
---
date: {YYYY-MM-DD}
repository: {owner}/{repo}
owner: {owner}
repo: {repo}
slug: {slug}
default_branch: {branch}
language: {primary_language}
collected_by: github-repo-analyst
---
```

## 出力ファイルの全体構造

```markdown
---
{YAMLフロントマター}
---

# GitHub API調査: {owner}/{repo}

## README要約
{抽出した概要・目的・使用方法}

## ディレクトリ構造分析
{アーキテクチャパターン、主要ディレクトリの役割}

## 依存関係
{主要ライブラリ一覧、バージョン情報}

## CI/CD構成
{テスト戦略、デプロイ方式}

## 外部仕様（API・CLI・設定）
{ユーザー向けインターフェースの整理}

## 内部仕様（アーキテクチャ）
{技術スタック、設計パターン、データフロー}

## リリース履歴
{メジャーバージョン一覧、リリース間隔}

## コミット履歴・開発活性度
{タイムライン、コミット頻度、マージ戦略}

## コントリビューター変遷
{トップコントリビューター、バス係数、開発体制}

## 将来方向性
{今後見込まれる改修、機能要望、進行中の変更}

## 制限事項・既知の課題
{公式に認識されている制限、コミュニティ報告}

## 関連リポジトリ（2ホップ）
{1ホップ目、2ホップ目のテーブル}

## メンテナンス健全性
{各種指標テーブル}

## 機械可読データ

以下のYAMLブロックはパイプラインスクリプトが自動抽出する。
エージェントは必ずこのセクションを出力の末尾に含めること。

**重要**: マーカー行（`# --- machine-readable-data ---` / `# --- end-machine-readable-data ---`）は
Markdownのコードブロック（` ```yaml `）の**外側**に記述すること。

```
## 機械可読データ

# --- machine-readable-data ---
basic_info:
  owner: "{owner}"
  repo: "{repo}"
  ...
# --- end-machine-readable-data ---
```

### データスキーマ

```yaml
basic_info:
  owner: "{owner}"
  repo: "{repo}"
  full_name: "{owner}/{repo}"
  description: "{description}"
  default_branch: "{branch}"
  language: "{primary_language}"
  stars: {N}
  forks: {N}
  created_at: "{ISO8601}"
  pushed_at: "{ISO8601}"
  license: "{license_id or null}"
  topics: [{topic1}, {topic2}]

tech_stack:
  languages: [{lang1}, {lang2}]
  frameworks: [{fw1}, {fw2}]
  build_tools: [{tool1}, {tool2}]
  test_frameworks: [{tf1}, {tf2}]
  ci_cd: [{ci1}]

related_repositories:
  fork_source: "{owner/repo or null}"
  primary_dependencies:
    - repo: "{owner/repo}"
      relationship: "dependency"
      description: "{1行説明}"
  recommended_for_deep_analysis:
    - repo: "{owner/repo}"
      reason: "{なぜ追加調査が必要か}"
      priority: "high | medium | low"

web_search_keywords:
  primary: "{リポジトリ名 or プロジェクト名}"
  secondary: ["{技術名1}", "{技術名2}", "{ドメイン名}"]
  competitors: ["{競合1}", "{競合2}"]
  ecosystem: "{エコシステム名（例: kintone, React, AWS）}"

code_analysis_hints:
  source_dirs: ["{src/}", "{lib/}"]
  test_dirs: ["{tests/}", "{__tests__/}"]
  config_files: ["{webpack.config.js}", "{tsconfig.json}"]
  entry_points: ["{src/index.ts}", "{src/main.js}"]
```

### エージェントが実際に出力する形式

エージェントは `## 機械可読データ` セクションの直下に、マーカー行で囲んだYAMLを**プレーンテキスト**として出力する（コードブロック不要）:

```
## 機械可読データ

# --- machine-readable-data ---
basic_info:
  owner: "volareinc"
  repo: "kintone-sales-management-system-frontend"
  full_name: "volareinc/kintone-sales-management-system-frontend"
  description: null
  default_branch: "develop"
  language: "JavaScript"
  stars: 0
  forks: 0
  created_at: "2021-11-09T07:06:05Z"
  pushed_at: "2026-05-11T02:21:35Z"
  license: null
  topics: []
tech_stack:
  languages: [JavaScript, TypeScript]
  frameworks: [React]
  build_tools: [Webpack, Babel]
  test_frameworks: [Vitest]
  ci_cd: [GitHub Actions]
related_repositories:
  fork_source: null
  primary_dependencies:
    - repo: "volareinc/carmo-kintone"
      relationship: "same_org"
      description: "同じkintoneカスタマイズ系リポジトリ"
  recommended_for_deep_analysis:
    - repo: "volareinc/dxm-estimate-workflow-tracker"
      reason: "見積ワークフロー追跡。new_estimate.tsと連携する可能性"
      priority: "medium"
web_search_keywords:
  primary: "kintone sales management"
  secondary: [kintone, JavaScript, TypeScript, 販売管理]
  competitors: [Salesforce, HubSpot, Zoho CRM]
  ecosystem: "kintone"
code_analysis_hints:
  source_dirs: [src/js/, src/ts/]
  test_dirs: [tests/]
  config_files: [webpack.config.js, tsconfig.json, vitest.config.js]
  entry_points: [src/js/revenue_management.js, src/ts/new_estimate.ts]
# --- end-machine-readable-data ---
```

## パイプラインスクリプトによる抽出

パイプラインスクリプトは以下のように機械可読データを抽出する:

```python
# scripts/data/extract-repo-analysis-data.py
# 入力: github-repo-analyst の出力ファイルパス
# 出力: JSON（stdout）

# 抽出ロジック:
# 1. ファイルから "# --- machine-readable-data ---" 〜 "# --- end-machine-readable-data ---" を抽出
# 2. YAMLとしてパース
# 3. JSONとして標準出力に書き出し
```

## 後続エージェントへの入力例

### → github-repo-analyst（参照先リポジトリ調査）

パイプラインスクリプトが `related_repositories.recommended_for_deep_analysis` を抽出し、プロンプトに埋め込む:

```
基準日は 2026-05-11 です。
以下のリポジトリを調査してください（概要レベル）:
- vercel/next.js: フォーク元。アーキテクチャの参考として重要
- volareinc/carmo-kintone: 同一org内の類似プロジェクト
出力先: Documents/works/scout_reports/github_repo_analysis/tmp/{slug}_refs.md
```

### → web-searcher

パイプラインスクリプトが `web_search_keywords` を抽出し、プロンプトに埋め込む:

```
以下のテーマについてWeb調査を行ってください。
テーマ: "{primary}" のエコシステム・競合・導入事例
キーワード: {secondary}
競合: {competitors}
エコシステム: {ecosystem}
出力先: Documents/works/scout_reports/github_repo_analysis/tmp/{slug}_web.md
purpose: tech_selection
```

### → code-analyst

パイプラインスクリプトが `code_analysis_hints` を抽出し、プロンプトに埋め込む:

```
以下のリポジトリのコードベースを分析してください。
リポジトリ: {owner}/{repo}
デフォルトブランチ: {default_branch}
主要言語: {language}
ソースディレクトリ: {source_dirs}
テストディレクトリ: {test_dirs}
設定ファイル: {config_files}
エントリポイント: {entry_points}
出力先: Documents/works/scout_reports/github_repo_analysis/tmp/{slug}_codebase.md
```
