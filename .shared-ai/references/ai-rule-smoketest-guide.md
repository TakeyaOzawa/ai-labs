# AI ルール適用スモークテストガイド

`.shared-ai/` 階層構造の変更後に、AI が正しくルールを読み込むかを手動確認するための手順書。

## 前提

- `python3.12 ~/scripts/setup/verify-shared-ai-structure.py` が全チェック PASS であること
- 静的検証（Check 1〜9）は「設定ファイルの整合性」を保証するが、「AI が実際にルールに従うか」は保証しない
- 本手順で AI のランタイム挙動を確認する

## テスト手順

### filematch-dispatcher 系

| # | プロンプト例 | 期待される挙動 | 確認ポイント |
|---|---|---|---|
| 1 | `.zshrc を確認してください` | env-sync.md を読み込む | 環境変数同期の注意事項に言及するか |
| 2 | `deploy.sh を修正してください` | shell-coding-standards.md を読み込む | シェルスクリプト規約に従うか |
| 3 | `scripts/setup/check-env.py を確認してください` | python-coding-standards.md + script-first-guide.md を読み込む | Python規約とスクリプトファースト原則に言及するか |
| 4 | `tests/Unit/UserTest.php を確認してください` | test-db-guard.md を読み込む | RefreshDatabase禁止に言及するか |
| 5 | `docs/domain/sales/overview.md を編集してください` | domain-frontmatter.md を読み込む | front-matter の updated_at 更新に言及するか |

### command-dispatcher 系

| # | プロンプト例 | 期待される挙動 | 確認ポイント |
|---|---|---|---|
| 6 | `PR を作成してください` | pr-creation.md を読み込む | ブランチ命名・コミットメッセージ規約に従うか |
| 7 | `Slack でメッセージを送信してください` | slack-user-lookup.md を読み込む | ユーザーID を lookup から取得するか |
| 8 | `Notion にページを作成してください` | notion-user-lookup.md を読み込む | ユーザーID を lookup から取得するか |
| 9 | `環境変数を追加してください` | env-sync.md を読み込む | .zshrc + platform-commands.sh の同期に言及するか |
| 10 | `.shared-ai/ にファイルを追加してください` | shared-ai-directory-guide.md を読み込む | 配置判断フローに従うか |

## 実行方法

### Kiro 環境

Kiro のチャットで上記プロンプトを入力し、応答を確認する。
steering の fileMatch が先に発火するため、filematch-dispatcher 系は自動的にカバーされる。

### claude 環境

```bash
claude --print --dangerously-skip-permissions "上記プロンプト"
```

出力に該当ルールの内容が反映されているか確認する。

## 判定基準

- **PASS**: AI の応答がルールの内容を反映している（ルール名の明示は不要）
- **FAIL**: AI がルールを無視している、または参照先が見つからないエラーが出る
- **SKIP**: 該当操作が発生しないプロンプトの場合

## 実施タイミング

- `.shared-ai/rules/` 配下のファイル追加・移動・削除時
- `resolve-shared-ai-rules.py` のパターン変更時
- steering の fileMatchPattern 変更時
- dispatcher のテーブル変更時

## 注意事項

- AI の出力は非決定的なため、1回の失敗で即座に問題とは判断しない
- 2回連続で同じ項目が FAIL の場合、設定を再確認する
- 全項目を毎回実施する必要はない。変更に関連する項目のみで十分
