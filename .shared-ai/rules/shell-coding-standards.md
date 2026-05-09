# シェルスクリプト コーディング規約

IEEE Std 1003.1（POSIX）およびISO/IEC 9945準拠のシェルスクリプト記述基準。
Google Shell Style Guide を参考に、プロジェクト固有の規約を追加。

## 1. シバン・初期設定

```bash
#!/bin/zsh
set -eu -o pipefail
```

- 新規スクリプトは `#!/bin/zsh` を使用（macOS標準、配列・パターンマッチが豊富）
- `#!/bin/bash` は既存スクリプトの互換性維持のみ。新規では使わない
- `set -eu -o pipefail` は全スクリプトの2行目に必須

## 2. ファイルヘッダー

```bash
# {script-name}: {1行の機能説明}
#
# 目的:
#   {なぜこのスクリプトが必要か。2〜3行で背景・動機を記述}
#
# 使い方:
#   {script-name}.sh <必須引数> [任意引数]
#
# 例:
#   {script-name}.sh 2026-05-07
#
# 出力: {JSON形式 / ファイル生成 / 標準出力}
# 依存: {外部コマンド（jq, npx等）があれば記載}
# 注意: {sudo必要、破壊的操作等の警告があれば記載}
```

| 項目 | 必須 | 記載基準 |
|------|------|----------|
| script-name + 1行説明 | ✅ | 全スクリプト |
| 目的 | 推奨 | 背景が自明でないもの |
| 使い方 | ✅ | 全スクリプト |
| 例 | ✅ | 引数があるもの |
| 出力 | ✅ | 全スクリプト |
| 依存 | 条件付き | 標準コマンド以外を使う場合 |
| 注意 | 条件付き | sudo、破壊的操作、前提条件がある場合 |

## 3. 命名規則

- ファイル名: `{動詞}-{対象}.sh`（例: `find-task.sh`, `manage-launchd.sh`）
- 動詞: find-, update-, create-, fetch-, check-, manage-, run-
- 変数名: `UPPER_SNAKE_CASE`
- 関数名: `lower_snake_case`

## 4. 関数

```bash
# 関数の説明（1行）
function_name() {
  local arg1="$1"
  local result=""

  # 処理
  result="computed_value"
  echo "$result"
}
```

- `local` で変数スコープを限定する
- 戻り値は `echo` で標準出力に返す（`return` は終了コードのみ）
- 関数定義は `name() {` 形式（`function` キーワードは使わない）
- 関数の前に1行コメントで説明を付ける

## 5. 制御構造

```bash
# if文
if [ condition ]; then
  command
elif [ condition ]; then
  command
else
  command
fi

# case文
case "$ACTION" in
  start)
    command
    ;;
  stop)
    command
    ;;
  *)
    usage
    ;;
esac

# forループ
for item in "${ARRAY[@]}"; do
  command
done

# whileループ（引数パース）
while [[ $# -gt 0 ]]; do
  case "$1" in
    --option) VALUE="$2"; shift 2 ;;
    *) break ;;
  esac
done
```

- インデント: スペース2文字
- `then`/`do` は同じ行に記述（`; then`, `; do`）
- 長い条件は `\` で改行

## 6. クォーティング

- 変数展開: ダブルクォート `"$VAR"` を常に使用
- リテラル文字列: シングルクォート `'literal'`（変数展開不要の場合）
- JSON文字列: ダブルクォート内でエスケープ `"{\"key\": \"$VALUE\"}"`
- コマンド置換: `"$(command)"` をダブルクォートで囲む

## 7. パイプ・リダイレクト

```bash
# 短いパイプ: 1行で記述
echo "$DATA" | jq '.status'

# 長いパイプ: 行末 | で改行
command_with_long_name \
  | grep "pattern" \
  | sort -u \
  | head -10

# リダイレクト
command > output.txt 2>&1        # stdout+stderrをファイルへ
command >> output.txt 2>&1       # 追記
echo "message" >&2               # stderrへ出力
```

- `2>&1` はコマンドの末尾に配置
- 人間向けメッセージは `>&2`（stderr）に出力

## 8. 出力形式

- スクリプトの出力は **JSON形式を標準** とする
- 成功時: `{"success": true, ...}`
- 失敗時: `{"success": false, "error": "..."}`
- 進捗表示は `echo "..." >&2` または `echo "[timestamp] message"`

## 9. エラーハンドリング

```bash
# 失敗を許容する場合は明示的に || true
command_that_may_fail || true

# エラー時のJSON出力
if ! some_command; then
  echo '{"success": false, "error": "説明"}'
  exit 1
fi

# usage関数パターン
usage() {
  echo '{"success": false, "error": "Usage: script.sh <args>"}'
  exit 1
}
[ $# -lt 1 ] && usage
```

## 10. 終了コード

| コード | 意味 | 用途 |
|--------|------|------|
| 0 | 成功 | 正常完了 |
| 1 | 一般エラー | 引数不正、処理失敗 |
| 2 | 使い方エラー | 引数不足、不正なオプション |
| 3 | 前提条件未達 | 必要なファイル/コマンドが存在しない |

## 11. セキュリティ

- 機密情報（トークン、パスワード）はスクリプトにハードコードしない
- 環境変数経由で受け取る: `"${MY_TOKEN:-}"`
- 一時ファイルは `mktemp` で作成し、trap で削除:
  ```bash
  TMPFILE=$(mktemp)
  trap 'rm -f "$TMPFILE"' EXIT
  ```
- `eval` は使用禁止
- 外部入力をコマンドに渡す場合はダブルクォートで囲む

## 12. セクション区切り

```bash
# ─── セクション名 ────────────────────────────────────────────────
# 補足説明（必要な場合のみ）
```

- 罫線は `─`（U+2500）で統一
- セクション名は日本語可

## 13. インラインコメント

- **Why（なぜ）を書く。What（何を）は書かない**
- 自明なコードにコメントを付けない
- 複雑なロジックには処理前にブロックコメントで意図を説明

## 14. ログ出力

- タイムスタンプ形式: `[$NOW]`（ISO 8601 + タイムゾーン）
  ```bash
  NOW=$(TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00)
  echo "[$NOW] メッセージ"
  ```
- 絵文字: 進捗表示に使用可（📋🔄✅❌⚠️）
- ログファイル: `~/logs/{script-name}.log`

## 15. 冪等性・テスト

- スクリプトは冪等に設計する（2回実行しても結果が同じ）
- `mkdir -p` で既存ディレクトリのエラーを回避
- `--dry-run` オプション: 破壊的操作を含むスクリプトでは提供を推奨

## 16. スクリプトの適用範囲

- **100行以下**: シェルスクリプトが適切
- **100〜300行**: シェルスクリプトで可。ただし関数分割を徹底する
- **300行超**: Python等への移行を検討する
- **複雑なデータ構造（ネストしたJSON操作等）**: `jq` で対応できなければPythonを使う
- **HTTP API呼び出しが主体**: Pythonの `requests` / `urllib` を推奨

## 17. 行の長さ

- 最大 **100文字** を目安とする（コメント含む）
- 超える場合は `\` で改行:
  ```bash
  very_long_command \
    --option1 value1 \
    --option2 value2
  ```
- ヘッダーコメントのセクション罫線は例外（視認性優先）

## 18. テスト構文

- 条件判定は `[[ ]]` を使用（zsh/bash拡張。`[ ]` より安全）
- `[[ ]]` の利点: 単語分割されない、`&&`/`||` が使える、正規表現マッチ `=~`
- ファイル存在: `[[ -f "$FILE" ]]`
- 文字列比較: `[[ "$A" == "$B" ]]`
- 数値比較: `(( NUM > 0 ))`
- コマンド成否: `if command; then` （`[[ ]]` 不要）

## 19. 外部コマンドの存在確認

```bash
# コマンドの存在確認
if ! command -v jq &>/dev/null; then
  echo '{"success": false, "error": "jq is required but not installed"}'
  exit 3
fi
```

- `command -v` を使用（`which` は非POSIX、環境依存）
- 必須コマンドはスクリプト冒頭で確認し、終了コード3で早期終了
- ヘッダーの「依存」項目にも記載する
