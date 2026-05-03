---
inclusion: always
---

# Slack ユーザーID逆引きガイド

Slackの投稿やメッセージを調査する際、ユーザーID（例: `U02LWEH3Z`）から人物を特定する必要がある場合は、**Slack APIを呼ぶ前に** `${HOME}/Documents/works/slack_users/` 配下のユーザーデータを参照すること。

## ユーザーID解決の優先順位

1. **`${HOME}/Documents/works/slack_users/` 配下のユーザーデータから検索**（API不要・コスト0）
2. ユーザーデータで見つからない場合のみ `mcp_slack_reference_home_slack_get_user_profile` を使用

## エージェントへの指示

Slackメッセージを処理するエージェント（slack-daily-scout、slack-digest-scout等）は、以下のルールに従うこと:

1. **ユーザーID→名前変換が必要な場合、まず `${HOME}/Documents/works/slack_users/` 配下のユーザーデータを読み込む**
2. 対象チャンネルの事業部が分かっている場合は該当ファイルのみ読み込む
3. 不明な場合は主要3事業部（MDX→DXM→MS）を順にreadFileで検索する
4. ユーザーデータで見つからないIDのみSlack APIで個別取得する
5. **`slack_get_users`（全件取得）は使わない**。ユーザーデータが同等の情報を持っている

### readFileでの検索例

```
# まず最新の日付ディレクトリを特定
ls -d ${HOME}/Documents/works/slack_users/20*/ | sort -r | head -1
# → ${HOME}/Documents/works/slack_users/2026-05-01/

# そのディレクトリ内のファイルを読む
readFile: ${HOME}/Documents/works/slack_users/2026-05-01/active/mdx.md
→ YAMLブロック内で対象ユーザーIDを検索
→ 見つかれば name フィールドを使用
→ 見つからなければ次のファイルへ
```

## アクティブユーザー（現職: deleted=false）

| ファイルパス | 事業部 | 人数 | 用途 |
|---|---|---:|---|
| `slack-users/{DATE}/active/mdx.md` | MDX（自動車産業DX） | 132 | セールス、CS、エンジニアリング、ナーチャリング等 |
| `slack-users/{DATE}/active/dxm.md` | DXM（DX＆マーケティング） | 113 | コンサル、コンテンツ、PMU等 |
| `slack-users/{DATE}/active/ms.md` | MS（メディア＆ソリューション） | 41 | Appliv、ギルドロケット、TOPICS等 |
| `slack-users/{DATE}/active/hr.md` | HR（人事本部） | 23 | 採用、労務、HRBP等 |
| `slack-users/{DATE}/active/cp.md` | CP（コーポレート本部） | 21 | 経営管理、法務、ICT等 |
| `slack-users/{DATE}/active/nyle-unset.md` | ナイル社員（title未設定） | 52 | title空のナイル社員 |
| `slack-users/{DATE}/active/other.md` | その他 | 11 | 分類外のtitle設定あり |
| `slack-users/{DATE}/active/guests.md` | 外部ゲスト | 445 | 外部パートナー・ゲスト |

※ `{DATE}` は最新の日付ディレクトリ名（例: `2026-05-01`）。特定方法は後述の「日付ディレクトリのルール」を参照。

## 非アクティブユーザー（退職・無効化済み: deleted=true）

| ファイルパス | 事業部 | 人数 |
|---|---|---:|
| `slack-users/{DATE}/inactive/mdx.md` | MDX | 63 |
| `slack-users/{DATE}/inactive/dxm.md` | DXM | 93 |
| `slack-users/{DATE}/inactive/ms.md` | MS | 29 |
| `slack-users/{DATE}/inactive/hr.md` | HR | 13 |
| `slack-users/{DATE}/inactive/cp.md` | CP | 25 |
| `slack-users/{DATE}/inactive/nyle-unset.md` | ナイル社員（title未設定） | 605 |
| `slack-users/{DATE}/inactive/other.md` | その他 | 183 |
| `slack-users/{DATE}/inactive/guests.md` | 外部ゲスト | 177 |

## 推奨ロード順序

ユーザーIDが不明な場合の探索順（`{DATE}` は最新日付ディレクトリ）:
1. `{DATE}/active/mdx.md` → `{DATE}/active/dxm.md` → `{DATE}/active/ms.md`（主要3事業部で大半カバー）
2. `{DATE}/active/hr.md` → `{DATE}/active/cp.md`（管理部門）
3. `{DATE}/active/nyle-unset.md` → `{DATE}/active/other.md`（title未設定）
4. 見つからなければ `{DATE}/inactive/*` を同順で探索
5. `{DATE}/active/guests.md` / `{DATE}/inactive/guests.md` は最後の手段
6. それでも見つからない場合のみ Slack API `get_user_profile` を使用

## 注意

- ユーザーデータは `${HOME}/Documents/works/slack_users/` 配下に日付ディレクトリで管理されている。readFileで直接読み込む
- 兼任者はMDX優先で1箇所のみに記載（重複なし）
- 更新: `slack-user-directory-update` hookで手動更新（隔週〜月1回）

## 日付ディレクトリのルール

`slack-users/` 配下は日付ディレクトリ（例: `2026-04-30/`）で管理される。更新のたびに新しい日付ディレクトリが作成される。

### 最新ディレクトリの特定手順

1. **まず `slack-users/README.md` が存在するか確認する**。存在すればその指示に従う
2. README.mdが無い場合は、**日付が最も新しいディレクトリを優先して使用する**
3. 日付ディレクトリ直下に `README.md` がある場合も、その指示に従う（例: 特定ファイルの参照先変更等）

### 確認コマンド

```bash
# README.mdの有無を確認
cat ${HOME}/Documents/works/slack_users/README.md 2>/dev/null

# 最新の日付ディレクトリを特定
ls -d ${HOME}/Documents/works/slack_users/20*/ 2>/dev/null | sort -r | head -1

# 日付ディレクトリ直下のREADME.mdを確認
LATEST=$(ls -d ${HOME}/Documents/works/slack_users/20*/ 2>/dev/null | sort -r | head -1)
cat "${LATEST}README.md" 2>/dev/null
```

