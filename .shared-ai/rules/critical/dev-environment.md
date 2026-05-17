# 開発環境ルール

## Python実行コマンド

- **`python3` は使用禁止。必ず `python3.12` を使用すること。**
- `python3.13` も使用しない。理由: Python 3.13のSSL証明書検証がNetskopeプロキシの証明書と互換性がなく、HTTPS通信時にSSLエラーが発生するため
- シェルスクリプト内、エージェントプロンプト内、手動実行時すべてに適用
- 理由: システムに複数バージョンのPythonがインストールされており、`python3` のリンク先が不定のため

```bash
# ✅ 正しい
python3.12 ~/scripts/fetch-rss-feeds.py --category tech --date 2026-05-07

# ❌ 間違い
python3 ~/scripts/fetch-rss-feeds.py --category tech --date 2026-05-07
```

## スクリプトファースト原則

エージェントが固定で実行する操作は、**コンテキスト圧縮のため可能な限りスクリプト化**すること。

### 判断基準

| スクリプト化すべき | プロンプト内に残してよい |
|---|---|
| 毎回同じ手順で実行する処理 | 状況に応じて判断が必要な処理 |
| 3行以上のコマンド列 | 1〜2行の単純なコマンド |
| 複数エージェントから共通で呼ばれる処理 | そのエージェント固有の1回限りの処理 |
| 日付計算・ファイル操作・JSON加工 | MCP呼び出し・readFile・対話的判断 |

### 技術選択ルール

1. **スクリプトは Python 3.12 で作成する**（OS間の挙動差を吸収するため）
2. **OS固有コマンド**（`caffeinate`, `launchctl`, `pmset`, `lsof` 等）は `~/scripts/platform-commands.sh` に集約し、Python から `subprocess` で呼び出す
3. **シェルスクリプトの新規作成は原則禁止**。`platform-commands.sh` への追記のみ許可
4. 外部パッケージ依存は最小化（標準ライブラリ優先）

### 新規作成時の規約参照

スクリプトを新規作成・大幅改修する場合は、以下をreadFileで読み込み従うこと:

- **Python コーディング規約**: `~/.shared-ai/rules/quality/python-coding-standards.md`
- **スクリプトファースト詳細ガイド**: `~/.shared-ai/references/script-first-guide.md`
- **シェル（platform-commands.sh追記時のみ）**: `~/.shared-ai/rules/quality/shell-coding-standards.md`

既存ファイルの編集時はsteeringの `fileMatch` で自動注入されるため、明示的な読み込みは不要。
