# Requirements 記述ガイド

specのrequirements.mdを作成する際は、本ガイドの記述ルールに従ってください。
本フォーマットはISO/IEC/IEEE 29148:2018（旧IEEE 830）のSRS構造を、Kiro SDD向けに簡略化したものです。

## 準拠規格

- ISO/IEC/IEEE 29148:2018 — Systems and software engineering — Requirements engineering
- ISO/IEC 14764:2022 — Software engineering — Software life cycle processes — Maintenance
- 簡略化の方針: 個人〜小規模チームのSDD運用に適した粒度に調整。セクション番号は29148の構造に対応。

## ISO/IEC 14764 保守分類との対応

変更種別（spec_type）はConventional Commitsに準拠しつつ、ISO/IEC 14764のソフトウェア保守4分類にも対応する。

| ISO/IEC 14764 分類       | 定義                               | 対応するspec_type | 備考                               |
| ------------------------ | ---------------------------------- | ----------------- | ---------------------------------- |
| Corrective（是正保守）   | 発見された問題の修正               | fix               | 不具合修正                         |
| Adaptive（適応保守）     | 環境変化・要件変化への対応         | feat              | 新規機能追加; 既存機能の追加・変更 |
| Perfective（完全化保守） | 性能・保守性・ユーザビリティの改善 | perf; refactor    | perf=性能改善; refactor=保守性改善 |
| Preventive（予防保守）   | 潜在的問題の予防的修正             | refactor          | 技術的負債の解消等                 |

## 変更種別の選択基準

| 種別     | 用途                                 | specが必要な規模の目安             |
| -------- | ------------------------------------ | ---------------------------------- |
| feat     | 新規機能追加; 既存機能への追加・変更 | 常に必要                           |
| fix      | 不具合修正                           | 再現手順・原因分析が必要な規模     |
| refactor | 外部動作を変えないコード構造改善     | 複数ファイルにまたがる変更         |
| perf     | パフォーマンス改善                   | ボトルネック分析・計測が必要な規模 |
| docs     | ドキュメント整備                     | 大規模な構造変更の場合のみ         |
