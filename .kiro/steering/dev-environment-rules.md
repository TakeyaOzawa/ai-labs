---
inclusion: always
---

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
