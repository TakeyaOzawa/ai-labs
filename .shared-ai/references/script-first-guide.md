# スクリプトファースト詳細ガイド

エージェントが固定で実行する操作をスクリプト化し、コンテキスト消費を最小化するためのルール。

---

## 1. 原則

**「プロンプトにコマンド列を書くな。スクリプトを呼べ。」**

エージェントのコンテキストウィンドウは有限リソース。毎回同じ手順を展開するのではなく、
スクリプトに閉じ込めて1行の呼び出しに圧縮する。

---

## 2. スクリプト化の判断基準

### スクリプト化すべき

- 毎回同じ手順で実行する処理（日付計算、ファイル探索、JSON加工、ログローテーション等）
- 3行以上のコマンド列
- 複数エージェント/hookから共通で呼ばれる処理
- エラーハンドリングやリトライが必要な処理
- OS固有コマンドを含む処理

### プロンプト内に残してよい

- 状況に応じて判断が必要な処理（MCP呼び出し結果に基づく分岐等）
- 1〜2行の単純なコマンド（`readFile` 1回等）
- そのエージェント固有の1回限りの処理

---

## 3. 技術選択ルール

### 3.1 言語選択

| 選択肢 | 使用条件 |
|---|---|
| **Python 3.12** | デフォルト。全ての新規スクリプト |
| **platform-commands.sh への追記** | OS固有コマンドが必要で、Pythonの `subprocess` では抽象化できない場合のみ |
| **シェルスクリプト新規作成** | **禁止** |

### 3.2 Python スクリプトの構成

```python
#!/usr/bin/env python3.12
"""
{スクリプト名}: {1行説明}
...
"""

import ...
from pathlib import Path

# OS固有コマンドが必要な場合のみ
PLATFORM_CMD = Path(__file__).parent / "platform-commands.sh"

def main() -> None:
    ...

if __name__ == "__main__":
    main()
```

### 3.3 OS固有コマンドの扱い

1. まず Python 標準ライブラリで実現できないか検討する
   - 日付計算 → `datetime`（`date -v-1d` の代替）
   - ファイル操作 → `pathlib`
   - JSON加工 → `json`（`jq` の代替）
   - プロセス管理 → `os.kill()`, `signal`
2. 標準ライブラリで不可能な場合のみ `platform-commands.sh` に追記する
   - 例: `caffeinate`（macOS固有のスリープ防止）
   - 例: `launchctl` / `systemctl`（サービス管理）
   - 例: `pmset`（電源管理）
   - 例: `lsof` のOS間差異（macOS vs Linux の出力形式の違い）
3. `platform-commands.sh` 内では `uname -s` で Mac/Linux を分岐する

### 3.4 外部依存

- **標準ライブラリ優先**（`json`, `pathlib`, `datetime`, `subprocess`, `argparse`, `urllib`）
- サードパーティパッケージは原則使用しない
- どうしても必要な場合は `dev-environment.md` に依存を明記する

---

## 4. プロンプト/hookでのスクリプト呼び出しパターン

### Before（❌ コンテキスト浪費）

```
以下のコマンドを実行してタスクファイルを生成:
1. ULIDを生成: npx --yes ulid
2. 現在時刻を取得: TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00
3. ディレクトリ作成: mkdir -p ~/Documents/works/agent_histories/scout_daily
4. JSONファイルを生成（以下のテンプレートに値を埋め込む）:
   { "task_id": "...", "task_name": "scout_daily", ... }
5. ファイルに書き出し
```

### After（✅ 1行で完結）

```
python3.12 ~/scripts/create-daily-tasks.py {BASE_DATE}
```

---

## 5. platform-commands.sh への追記ルール

新しいOS固有コマンドを追加する場合:

1. 既存のコマンド一覧（ファイル冒頭のコメント）を確認し、重複がないか確認
2. `case "$COMMAND" in` ブロックに新しいケースを追加
3. macOS (`Darwin`) と Linux の両方の実装を記述
4. Linux側で該当機能がない場合は適切なフォールバック（no-op or エラーメッセージ）を返す
5. 出力は JSON 形式を標準とする

---

## 6. チェックリスト（プロンプト/hook編集時）

プロンプトやhookを編集する際、以下を確認:

- [ ] 3行以上のコマンド列がプロンプト内に直書きされていないか
- [ ] 日付計算を `date` コマンドで行っていないか（→ Python の `datetime` を使う）
- [ ] `jq` を使っていないか（→ Python の `json` を使う）
- [ ] 同じ処理が複数のプロンプト/hookに重複していないか（→ スクリプトに共通化）
- [ ] OS固有コマンドが直接呼ばれていないか（→ `platform-commands.sh` 経由にする）
