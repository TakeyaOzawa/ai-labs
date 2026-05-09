# Notion ユーザーID逆引きガイド

Notionのページ作成者・編集者のユーザーID（UUID形式、例: `0af04c43-1c2c-49a4-aa28-8ad7f783bd13`）から人物を特定する必要がある場合は、**Notion APIを呼ぶ前に** `${HOME}/Documents/works/notion_users/` 配下のユーザーデータを参照すること。

## ユーザーID解決の優先順位

1. **`${HOME}/Documents/works/notion_users/` 配下の `people.md` から検索**（API不要・コスト0）
2. `people.md` で見つからない場合は **`bots.md` を検索**
3. どちらでも見つからない場合のみ **`mcp_notion_home_notion_get_users` を使用**

## データ構造

### ファイル配置

```
${HOME}/Documents/works/notion_users/
└── {DATE}/              # 日付ディレクトリ（例: 2026-05-03）
    ├── people.md        # 人物ユーザー（72名）
    └── bots.md          # ボットユーザー（42件）
```

### YAMLフォーマット

各ファイル内のYAMLブロックは以下の形式:

```yaml
{notion_user_id}:
  name: "姓 名ローマ字"
  type: "person" | "bot"
  email: "xxx@nyle.co.jp" | "-"
```

## 探索手順

### Step 1: 最新ディレクトリの特定

```bash
ls -d ${HOME}/Documents/works/notion_users/20*/ 2>/dev/null | sort -r | head -1
```

### Step 2: people.md を読み込み、対象IDを検索

```
readFile: ${HOME}/Documents/works/notion_users/{DATE}/people.md
→ YAMLブロック内で対象ユーザーIDを検索
→ 見つかれば name フィールドを使用
```

### Step 3: 見つからなければ bots.md を検索

```
readFile: ${HOME}/Documents/works/notion_users/{DATE}/bots.md
→ YAMLブロック内で対象ユーザーIDを検索
→ 見つかれば name フィールドを使用
```

### Step 4: それでも見つからない場合のみ Notion API

```
mcp_notion_home_notion_get_users で個別取得
```

## 人名からNotion IDを引く場合

「Aさんが更新したページ」のようなクエリでは、人名→Notion user_idの正引きが必要:

1. `people.md` を読み込み、`name` フィールドで部分一致検索
2. 該当するユーザーの Notion user_id を取得
3. そのIDを `notion_search` の `created_by_user_ids` や `filters` で使用

### 検索のコツ

- 姓のみ・名のみでも部分一致で探す（例: 「田中」→ `田中 創基Souki Tanaka`）
- ローマ字表記も含まれるため、ローマ字での検索も有効
- emailのローカルパート（`@` 前）でも特定可能

## SlackユーザーIDとの紐付け

Notion IDとSlack IDは異なる体系だが、**email** を共通キーとして紐付け可能:

1. Slackユーザーデータ（`${HOME}/Documents/works/slack_users/`）から対象者のemailを特定
2. Notionユーザーデータの `email` フィールドで同じアドレスを検索
3. 一致すればそのNotion user_idを使用

## 注意事項

- ユーザーデータは `${HOME}/Documents/works/notion_users/` 配下に日付ディレクトリで管理
- `people.md` に大半のアクティブユーザーが含まれる（72名）
- ボットアカウント（インテグレーション）は `bots.md` に分離（42件）
- **`notion_get_users`（全件取得API）は最後の手段**。ローカルデータが同等の情報を持っている
- 更新頻度: 必要に応じて手動更新
