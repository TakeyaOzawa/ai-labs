# fix: scoutレポートの曜日表示が不正確

## 変更種別

fix

## 概要

- daily/weeklyパイプラインで生成されるscoutレポートのH1タイトルに含まれる曜日が間違っていることが多い
- AIモデルが日付から曜日を推測しているため不正確になる
- シェルコマンドで曜日を確定させる仕組みを導入する

## 問題・背景

- 各scoutエージェントは出力レポートのH1に `{YYYY-MM-DD} ({曜日})` を含める
- 基準日はシェルコマンドまたはプロンプト引数で正しく取得されている
- しかし曜日の計算方法が未指定のため、AIモデルが日付→曜日を推測して間違える
- 特にパイプライン経由（基準日が引数で渡される）の場合に顕著

## 修正方針

「対象日付の決定」セクションに曜日取得コマンドを追加し、AIモデルの推測に頼らない設計にする。

```bash
# macOS
date -j -f "%Y-%m-%d" "{基準日}" "+%A"
# または LANG=ja_JP.UTF-8 で日本語曜日を直接取得
```

パイプライン経由で基準日が渡される場合も、エージェントがシェルコマンドで曜日を確定させる。

## 修正対象

1. `.shared-ai/prompts/tech-trend-scout.md`
2. `.shared-ai/prompts/biz-car-trend-scout.md`
3. `.shared-ai/prompts/academic-trend-scout.md`
4. `.shared-ai/prompts/slack-trend-scout-merge.md`
5. `.shared-ai/prompts/tech-event-scout.md`
6. `.shared-ai/prompts/lifestyle-event-scout.md`

## タスク分解

### Task 1: 曜日取得コマンドの決定

- macOS環境で日本語曜日を取得するコマンドを確定
- `date -j -f "%Y-%m-%d" "2026-05-10" "+%A"` → Saturday → 日本語変換が必要
- または `LANG=ja_JP.UTF-8 date -j -f "%Y-%m-%d" "2026-05-10" "+%a曜日"` → 土曜日

### Task 2: 6つのプロンプトの「対象日付の決定」セクションを修正

- 曜日取得コマンドを追記
- 「曜日はAIモデルの推測に頼らず、シェルコマンドで確定させること」を明記

## 影響範囲

- 6つのscoutエージェントの出力レポートのH1タイトル
- Slack通知メッセージ（H1がそのまま通知タイトルになる）

## テスト計画

- [ ] macOS環境で曜日取得コマンドが正しく動作すること
- [ ] 既知の日付で曜日が正しいことを確認（例: 2026-05-10 = 日曜日）
