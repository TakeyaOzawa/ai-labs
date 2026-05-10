# slack-trend-scout-channel 出力フォーマット

指定された中間ファイルパスに以下の形式でMarkdownを書き出す。

## 通常出力

```markdown
---
date: {YYYY-MM-DD}
channel_id: {チャンネルID}
channel_name: {チャンネル名}
collected_by: slack-trend-scout-channel
message_count: {N}
thread_count: {N}
reply_count: {N}
---

### 新規トピック

#### {トピック要約}

- **投稿**: [{ts}](https://volare.slack.com/archives/{channel_id}/p{tsのドットを除去した値})
- **スレッド**: [{thread_ts}](https://volare.slack.com/archives/{channel_id}/p{thread_tsのドットを除去した値})（スレッドがある場合）
- **投稿者**: {ユーザー名}
- **投稿日時**: {YYYY-MM-DD HH:MM} JST
- **概要**: {2〜3文の要約}
- **返信数**: {N}件
- **リアクション**: {リアクション一覧}（例: ✅済×1, 👀eyes×2）
- **関連リンク**: [#{PR番号} {PRタイトル}](https://github.com/{org}/{repo}/pull/{PR番号}) / [{Notionページ名}]({NotionURL})
- **スレッド結論**: {結論が出ている場合はその内容。未決の場合は「未決」}

### 過去スレッドへの返信

#### {元トピック要約}（元投稿: {YYYY-MM-DD}）

- **元投稿**: [{root.ts}](https://volare.slack.com/archives/{channel_id}/p{root.tsのドットを除去した値})
- **スレッド**: [{thread_ts}](https://volare.slack.com/archives/{channel_id}/p{thread_tsのドットを除去した値})
- **元投稿者**: {ユーザー名}
- **本日の返信数**: {N}件
- **本日の返信者**: {ユーザー名1}, {ユーザー名2}
- **本日の返信概要**: {返信内容の要約}
- **スレッド全体の状況**: {議論中/結論済み/放置中}

### 未対応・要注意アイテム

| 投稿 | 投稿者 | 概要 | リアクション | 返信数 |
| --- | --- | --- | --- | --- |
| [{ts}](https://volare.slack.com/archives/{channel_id}/p{tsドットなし}) | {ユーザー名} | {1行概要} | なし | 0 |
```

## 投稿がない場合

```markdown
---
date: {YYYY-MM-DD}
channel_id: {チャンネルID}
channel_name: {チャンネル名}
collected_by: slack-trend-scout-channel
message_count: 0
thread_count: 0
reply_count: 0
---

対象日の投稿はありませんでした。
```
