---
inclusion: fileMatch
fileMatchPattern: "scripts/**/*.py"
---

# Python スクリプト コーディング規約

PEP 8（Style Guide）、PEP 257（Docstring Conventions）、PEP 484（Type Hints）準拠。
Google Python Style Guide を参考に、プロジェクト固有の規約を追加。
ISO/IEC 25010:2023（ソフトウェア品質モデル）の保守性・信頼性を考慮。

## 1. シバン・エンコーディング

```python
#!/usr/bin/env python3.12
```

- `#!/usr/bin/env python3.12` を使用（バージョンを明示）
- Python 3.12: `str | None` 等のunion型構文がネイティブで使用可能（3.10+）
- **Python 3.13は使用不可**: Netskope SSLインターセプトの中間CA証明書が
  OpenSSL 3.x の厳格な Basic Constraints 検証を通過しないため、
  HTTPS通信が `CERTIFICATE_VERIFY_FAILED` で失敗する
- エンコーディング宣言は不要（Python 3はUTF-8デフォルト）

## 2. モジュールDocstring（ファイルヘッダー）

```python
"""
{スクリプト名}: {1行の機能説明}

目的:
    {なぜこのスクリプトが必要か。2〜3行で背景・動機を記述}

使い方:
    python3 scripts/{script-name}.py <必須引数> [任意引数]
    python3 scripts/{script-name}.py --option value

例:
    python3 scripts/fetch-rss-feeds.py --category tech --date 2026-05-05

出力: {JSON / ファイル生成 / 標準出力}
依存: {外部パッケージがあれば記載。標準ライブラリのみなら省略}
"""
```

| 項目 | 必須 | 記載基準 |
|------|------|----------|
| 1行説明 | ✅ | 全スクリプト |
| 目的 | 推奨 | 背景が自明でないもの |
| 使い方 | ✅ | 全スクリプト |
| 例 | ✅ | 引数があるもの |
| 出力 | ✅ | 全スクリプト |
| 依存 | 条件付き | 標準ライブラリ以外を使う場合 |

## 3. import順序

```python
# 標準ライブラリ
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# サードパーティ（あれば）
import requests

# ローカル（あれば）
from utils import helper
```

- PEP 8準拠: 標準ライブラリ → サードパーティ → ローカル
- 各グループ間に空行1行
- `from` importは同一モジュールからまとめる
- ワイルドカードimport（`from module import *`）は禁止

## 4. 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| ファイル名 | `{動詞}-{対象}.py`（ケバブケース） | `fetch-rss-feeds.py` |
| 関数名 | `snake_case` | `fetch_all_users()` |
| 変数名 | `snake_case` | `base_date`, `output_dir` |
| 定数 | `UPPER_SNAKE_CASE` | `FEEDS`, `MAX_RETRIES` |
| クラス名 | `PascalCase` | `FeedParser` |
| プライベート | `_prefix` | `_parse_entry()` |

## 5. 型ヒント

```python
def fetch_feed(url: str, timeout: int = 30) -> str | None:
    """フィードを取得してエントリのリストを返す。"""
    ...

def classify_user(title: str, email: str) -> str:
    """ユーザーを事業部に分類する。"""
    ...
```

- 関数の引数と戻り値に型ヒントを付ける（PEP 484）
- Python 3.12: `str | None`, `list[dict]`, `dict[str, Any]` 等のビルトイン型をそのまま使用
- `from __future__ import annotations` は不要（3.10+でネイティブサポート）
- 複雑な型は `TypeAlias` で定義

## 6. Docstring

```python
def fetch_all_users(token: str, output_dir: str) -> None:
    """Slack APIから全ユーザーを取得しJSONファイルに保存する。

    Args:
        token: Slack Bot Token（xoxb-...）
        output_dir: 出力先ディレクトリパス

    Raises:
        ValueError: トークンが空の場合
        urllib.error.HTTPError: API呼び出し失敗時
    """
```

- Google Style Docstring形式（Args/Returns/Raises）
- 1行で収まる場合は1行Docstring: `"""分類結果を返す。"""`
- 全publicな関数にDocstringを付ける

## 7. エラーハンドリング

```python
# 具体的な例外をキャッチ（bare exceptは禁止）
try:
    response = urllib.request.urlopen(req, timeout=30)
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}", file=sys.stderr)
    sys.exit(1)
except urllib.error.URLError as e:
    print(f"URL Error: {e.reason}", file=sys.stderr)
    sys.exit(1)

# リトライパターン
for attempt in range(max_retries):
    try:
        result = do_something()
        break
    except TransientError:
        if attempt == max_retries - 1:
            raise
        time.sleep(2 ** attempt)
```

- `except Exception` は最小限に。具体的な例外型を指定
- `except:` （bare except）は禁止
- リトライは指数バックオフ

## 8. 出力形式

- スクリプトの最終出力は **JSON形式を標準** とする（shスクリプトと統一）
- 成功時: `{"success": true, ...}`
- 失敗時: `{"success": false, "error": "..."}`
- 進捗表示は `print(..., file=sys.stderr)`

```python
# 最終出力
result = {"success": True, "count": len(items), "output": str(output_path)}
print(json.dumps(result, ensure_ascii=False))

# 進捗表示（stderrへ）
print(f"→ {feed_name}... ✅ {count}件", file=sys.stderr)
```

## 9. 引数パース

```python
def main():
    parser = argparse.ArgumentParser(description="フィード取得スクリプト")
    parser.add_argument("--category", required=True, choices=["tech", "biz", "academic"])
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--output", help="出力先パス（省略時: デフォルト）")
    args = parser.parse_args()
    ...

if __name__ == "__main__":
    main()
```

- `argparse` を使用（`sys.argv` 直接操作は避ける）
- `if __name__ == "__main__":` ガードを必須とする
- `main()` 関数にロジックを集約

## 10. 定数・設定

```python
# ─── 定数定義 ────────────────────────────────────────────────────

MAX_RETRIES = 5
REQUEST_TIMEOUT = 30
JST = timezone(timedelta(hours=9))

FEEDS: dict[str, list[dict]] = {
    "tech": [...],
    "biz": [...],
}
```

- 定数はモジュールレベルで `UPPER_SNAKE_CASE`
- マジックナンバーは定数化する
- 大きな設定データ（FEEDS等）はセクション区切りで視認性を確保

## 11. セクション区切り

```python
# ─── セクション名 ────────────────────────────────────────────────
```

- shスクリプトと同じ `─`（U+2500）形式で統一
- 長いスクリプトでの視認性向上に使用

## 12. ファイル操作

```python
from pathlib import Path

# pathlib を優先使用（os.path より可読性が高い）
output_dir = Path.home() / "Documents" / "works" / "output"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / f"{date}_{name}.md"
output_file.write_text(content, encoding="utf-8")
```

- `pathlib.Path` を優先（`os.path.join` より可読性が高い）
- ファイル書き込みは `encoding="utf-8"` を明示
- ディレクトリ作成は `mkdir(parents=True, exist_ok=True)`

## 13. HTTP通信

```python
# 標準ライブラリのみで実装（外部依存を避ける）
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {token}")
req.add_header("User-Agent", "scout-pipeline/1.0")

with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
    data = json.loads(resp.read().decode("utf-8"))
```

- 標準ライブラリ（`urllib`）を優先（外部依存を最小化）
- `requests` は複雑なHTTP操作が必要な場合のみ
- タイムアウトを必ず指定
- User-Agentを設定

## 14. セキュリティ

- 機密情報はスクリプトにハードコードしない
- 環境変数経由で受け取る: `os.environ.get("TOKEN", "")`
- 一時ファイルは `tempfile` モジュールを使用
- `eval()` / `exec()` は使用禁止
- 外部入力のバリデーションを行う

## 15. 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功 |
| 1 | 一般エラー |
| 2 | 引数エラー（argparseが自動で返す） |
| 3 | 前提条件未達（必要なファイル/環境変数がない） |

## 16. 行の長さ・フォーマット

- 最大 **100文字**（PEP 8の79文字より緩和。可読性優先）
- インデント: スペース4文字
- 文字列フォーマット: f-string を優先（`f"{name}: {value}"`）
- 長い行は括弧内で改行:
  ```python
  result = (
      very_long_function_name(
          argument_one,
          argument_two,
      )
  )
  ```
