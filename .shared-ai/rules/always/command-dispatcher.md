# コマンド/操作別ルール適用ディスパッチャー

以下の操作を行う場合、対応するファイルをreadFileで読み込み従うこと。
該当しない場合は何もしなくてよい。既に同じファイルが読み込み済みの場合はスキップしてよい。

> **注意**: Kiro環境ではsteeringの `inclusion: always` が先に同じルールを注入済みの場合がある。
> その場合、このディスパッチャーからの重複読み込みは不要。

| 操作・コマンド | readFile対象 |
|---|---|
| Python実行（python3.12, pip, スクリプト実行等） | `~/.shared-ai/rules/contextual/dev-environment.md` |
| GWSサービス操作（Gmail, Drive, Calendar, Docs, Sheets等） | `~/.shared-ai/rules/contextual/gws-integration.md` |
| PR作成・ブランチ操作・コミット | `~/.shared-ai/rules/contextual/pr-creation.md` |
| 環境変数の追加・変更（export行の編集等） | `~/.shared-ai/rules/contextual/env-sync.md` |
| Slack操作（メッセージ送信、チャンネル操作、ユーザー検索等） | `~/.shared-ai/lookups/slack-user-lookup.md`, `~/.shared-ai/lookups/slack-channel-mapping.md` |
| Notion操作（ページ作成、DB操作、ユーザー検索等） | `~/.shared-ai/lookups/notion-user-lookup.md` |
| .shared-ai/配下へのファイル追加・移動 | `~/.shared-ai/references/shared-ai-directory-guide.md` |
