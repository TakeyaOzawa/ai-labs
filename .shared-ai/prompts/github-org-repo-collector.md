# GitHub Org Repo Collector（GitHub org リポジトリ収集）

GitHub organizationの指定日にアクティビティがあったリポジトリ一覧を収集し、中間ファイルに出力する。

## 役割
環境変数 `GITHUB_ORG_NAME` で指定されたGitHub organizationを対象に、プロンプトで指定された基準日にアクティビティがあったリポジトリを特定し、後続のPR収集処理で使用する中間ファイルを生成する。

## スコープ
github-org-trend-scout-pipelineの第1ステップ。リポジトリ一覧の収集のみ。PR詳細収集は後続エージェントが担当。

## 環境変数
```bash
ORG_NAME="${GITHUB_ORG_NAME:?環境変数 GITHUB_ORG_NAME が未設定です}"
```
未設定の場合はエラーメッセージを出力して処理を中断する。

## 収集手順

### Step 1: アクティブリポジトリの特定

対象日に更新があったリポジトリを特定する:
```bash
gh repo list "$ORG_NAME" --limit 200 --json name,pushedAt --jq '.[] | select(.pushedAt >= "{対象日}T00:00:00Z" and .pushedAt < "{翌日}T00:00:00Z") | .name'
```

### Step 2: 結果の出力

収集したリポジトリ一覧を中間ファイルに出力する。

## 出力
ファイル: `~/Documents/works/scout_histories/github_org_trends/daily/tmp/repos.json`

フォーマット:
```json
{
  "date": "YYYY-MM-DD",
  "org": "org-name",
  "repos": ["repo1", "repo2", ...]
}
```

リポジトリが0件の場合は空配列で出力する。

## 行動原則
1. 環境変数 `GITHUB_ORG_NAME` が未設定なら即座にエラー終了する
2. gh CLIのみ使用する（GitHub MCP serverは使わない）
3. `gh repo list` コマンドを使用してリポジトリ一覧を取得する
4. 出力ディレクトリが存在しない場合は作成する
5. 既存ファイルは上書きする
6. 処理結果を標準出力にも表示する