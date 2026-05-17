# fix: scoutレポートの日付取得をクロスプラットフォーム対応

## 変更種別

fix

## 概要

- daily/weeklyパイプラインで使用される日付取得コマンドをmacOS/Linux共通で動作する `get-jst-date.py` に統一
- macOS固有コマンド（`date -v-1d`, `date -j`）を排除
- 曜日出力を廃止（AIモデルの推測誤りの根本原因を除去）

## 修正対象

1. `scripts/get-jst-date.py` — 新規作成（JST日付取得スクリプト）
2. `.shared-ai/prompts/` 配下の全scoutエージェント — 日付取得コマンドを `get-jst-date.py` に統一
3. 出力テンプレートから `({曜日})` を削除

## テスト計画

- [x] macOS環境で `get-jst-date.py` が正しく動作すること
- [x] `--yesterday` で前日が正しく取得されること
- [ ] Linux環境での動作確認（WSL2等）
