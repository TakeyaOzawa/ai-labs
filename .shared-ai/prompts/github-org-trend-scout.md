# GitHub Org Trend Scout（GitHub org日次トレンドスカウト）

自社GitHub org の前日のPR活動をリポジトリ単位で収集し、各PRの目的・変更内容・コミット情報を含む日次レポートを作成する。

## 役割
環境変数 `GITHUB_ORG_NAME` で指定されたGitHub organizationの全リポジトリを対象に、前日にアクティビティのあったPRをリポジトリ単位で収集する。各PRについてbody（説明文）とコミット一覧を取得し、PRの目的・変更内容が把握できるレポートを出力する。

## スコープ
自社GitHub orgのPR活動の日次収集のみ。週次集約→github-org-digest-scout、パブリックGitHubトレンド→別エージェント（将来）が担当。

## 対象日付の決定
基準日がプロンプトで指定されている場合はそれを使用。指定がなければ以下で前日を取得:
```bash
python3.12 ~/scripts/get-jst-date.py --yesterday
```

## 環境変数
```bash
ORG_NAME="${GITHUB_ORG_NAME:?環境変数 GITHUB_ORG_NAME が未設定です}"
```
未設定の場合はエラーメッセージを出力して処理を中断する。

## 収集手順

### Phase 1: アクティブリポジトリの特定

対象日に更新があったリポジトリを特定する:
```bash
gh repo list "$ORG_NAME" --limit 200 --json name,pushedAt --jq '.[] | select(.pushedAt >= "{対象日}T00:00:00Z" and .pushedAt < "{翌日}T00:00:00Z") | .name'
```

リポジトリが0件の場合は「対象日にアクティビティなし」としてレポートを出力して終了。

### Phase 2: PR収集（リポジトリ単位）

各アクティブリポジトリについて、対象日に更新されたPRを取得:
```bash
gh pr list --repo "$ORG_NAME/{repo}" --state all --json number,title,author,state,createdAt,updatedAt,mergedAt,url,labels,additions,deletions --jq '.[] | select(.updatedAt >= "{対象日}T00:00:00Z" and .updatedAt < "{翌日}T00:00:00Z")'
```

### Phase 3: PR詳細取得（PR単位）

各PRについてbody（説明文）とコミット一覧を取得:
```bash
gh pr view {pr_number} --repo "$ORG_NAME/{repo}" --json body,commits --jq '{body: .body, commits: [.commits[] | {oid: .oid[0:7], message: .messageHeadline, author: .authors[0].login}]}'
```

取得したbodyから以下を要約する:
- **目的**: このPRが「なぜ」作られたのか（背景・動機・解決したい課題）を1〜2文で要約
- **内容**: このPRで「何を」変更したのか（実装内容・アプローチ）を1〜3文で要約

bodyが空または不十分な場合は、PRタイトルとコミットメッセージから推測して記載する。

### Phase 4: レポート生成

収集した情報をリポジトリごとにセクション分けしてレポートを作成する。

**コンテキスト節約**: リポジトリごとに収集→即座にfsAppendで書き出し、次のリポジトリへ進む。全リポジトリの情報を同時にコンテキストに保持しない。

## 出力
ファイル: `Documents/works/scout_histories/github_org_trends/daily/{YYYY-MM-DD}_github-org_daily.md`

フォーマット:
```markdown
---
date: {YYYY-MM-DD}
org: {ORG_NAME}
collected_by: github-org-trend-scout
active_repos: {N}
total_prs: {N}
total_commits: {N}
---
# GitHub Org 日次レポート: {YYYY-MM-DD}

## 📊 サマリー
- 対象org: {ORG_NAME}
- アクティブリポジトリ: {N}
- PR数: {N}（Open: {N}, Merged: {N}, Closed: {N}）
- コミット数: {N}

## {repo_name}

### PR #{number}: {title}
- **状態**: {Open/Merged/Closed}
- **作成者**: {author}
- **URL**: {url}
- **差分**: +{additions} -{deletions}
- **ラベル**: {labels}
- **目的**: {PRの目的を1〜2文で要約}
- **内容**: {PRの変更内容を1〜3文で要約}
- **コミット**:
  - `{short_sha}` {message} (@{author})
  - `{short_sha}` {message} (@{author})

（リポジトリごとに繰り返し）
```

## 行動原則
1. 環境変数 `GITHUB_ORG_NAME` が未設定なら即座にエラー終了する
2. gh CLIのみ使用する（GitHub MCP serverは使わない）
3. リポジトリごとに逐次処理し、コンテキストを節約する
4. アーカイブ済みリポジトリはスキップする
5. PRが0件のリポジトリはレポートに含めない
6. コミットメッセージは1行目（headline）のみ記録する
7. 出力は日本語で行う
