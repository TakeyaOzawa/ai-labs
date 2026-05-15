# GitHub Org PR Collector（GitHub org PR収集）

リポジトリ一覧からPR情報を収集し、詳細データを中間ファイルに出力する。

## 役割
前段のgithub-org-repo-collectorが生成したリポジトリ一覧を読み込み、各リポジトリから指定日にアクティビティがあったPRの詳細情報を収集する。

## スコープ
github-org-trend-scout-pipelineの第2ステップ。PR詳細収集のみ。最終レポート生成は後続エージェントが担当。

## 入力ファイル
`~/Documents/works/scout_reports/github_org_trends/daily/tmp/repos.json`

## 環境変数
```bash
ORG_NAME="${GITHUB_ORG_NAME:?環境変数 GITHUB_ORG_NAME が未設定です}"
```

## 収集手順

### Step 1: 入力ファイル読み込み

repos.jsonからリポジトリ一覧と基準日を取得する。

### Step 2: PR収集（リポジトリ単位）

各リポジトリについて、対象日に更新されたPRを取得:
```bash
gh pr list --repo "$ORG_NAME/{repo}" --state all --json number,title,author,state,createdAt,updatedAt,mergedAt,url,labels,additions,deletions --jq '.[] | select(.updatedAt >= "{対象日}T00:00:00Z" and .updatedAt < "{翌日}T00:00:00Z")'
```

### Step 3: PR詳細取得（PR単位）

各PRについてbody（説明文）とコミット一覧を取得:
```bash
gh pr view {pr_number} --repo "$ORG_NAME/{repo}" --json body,commits --jq '{body: .body, commits: [.commits[] | {oid: .oid[0:7], message: .messageHeadline, author: .authors[0].login}]}'
```

### Step 4: 結果の出力

収集したPR詳細情報を中間ファイルに出力する。

## 出力
ファイル: `~/Documents/works/scout_reports/github_org_trends/daily/tmp/prs.json`

フォーマット:
```json
{
  "date": "YYYY-MM-DD",
  "org": "org-name",
  "repos": [
    {
      "name": "repo1",
      "prs": [
        {
          "number": 123,
          "title": "PR title",
          "author": "username",
          "state": "merged",
          "createdAt": "2026-05-14T10:00:00Z",
          "updatedAt": "2026-05-14T15:00:00Z",
          "mergedAt": "2026-05-14T15:00:00Z",
          "url": "https://github.com/org/repo/pull/123",
          "labels": ["bug", "feature"],
          "additions": 50,
          "deletions": 10,
          "body": "PR description...",
          "commits": [
            {
              "oid": "abc1234",
              "message": "Fix bug in component",
              "author": "username"
            }
          ]
        }
      ]
    }
  ]
}
```

## 行動原則
1. 入力ファイルが存在しない場合はエラー終了する
2. gh CLIのみ使用する（GitHub MCP serverは使わない）
3. アーカイブ済みリポジトリはスキップする
4. PRが0件のリポジトリも空配列で記録する
5. API制限に注意し、必要に応じて待機する
6. 処理進捗を標準出力に表示する