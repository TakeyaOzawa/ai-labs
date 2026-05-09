# Design 記述ガイド

specのdesign.mdを作成する際は、本ガイドの記述ルールに従ってください。
本フォーマットはIEEE 1016:2009（SDD）の構造を、Kiro SDD向けに簡略化したものです。

## 準拠規格

- IEEE 1016:2009 — Software Design Descriptions
- ISO/IEC/IEEE 42010:2011 — Architecture description（アーキテクチャビューポイントの考え方を参照）
- ISO/IEC 14764:2022 — Software engineering — Software life cycle processes — Maintenance
- 簡略化の方針: IEEE 1016のDesign Viewpoint概念を、実用的なセクション構成に変換。

## ISO/IEC 14764 保守分類との対応

design.mdの構成は、requirements.mdの `spec_type` に応じて変更種別ごとの追加セクションを持つ。
ISO/IEC 14764の保守分類との対応はグローバルsteering `requirements-format-guide.md` を参照。

設計書では特に以下の観点で保守分類を意識する:

| ISO/IEC 14764 分類                  | 設計書での重点セクション                         |
| ----------------------------------- | ------------------------------------------------ |
| Corrective（是正: fix）             | 修正方針、副作用の回避策                         |
| Adaptive（適応: feat）              | アーキテクチャ、コンポーネント設計、データモデル |
| Perfective（完全化: perf/refactor） | ボトルネック分析、変更前後の対比、互換性の確保   |
| Preventive（予防: refactor）        | 変更前後の対比、互換性の確保                     |

## 記述ルール

- mermaid図を積極的に使用する（アーキテクチャ図、シーケンス図、ER図、ステートマシン図）
- ファイルパスは `app/` からの相対パスで記載する
- 要件トレーサビリティマトリクスで、requirements.mdの要件IDと設計コンポーネントを対応づける

## 影響分析のフロー

デグレ・既存機能への影響は、requirements → design → tasks の3段階で分析する:

```
requirements.md §6 影響範囲
  → 「何に影響するか」を特定（影響を受ける機能、リグレッションリスク、後方互換性）

design.md §10.2 既存機能への影響
  → 「どう対処するか」を設計（回避策、互換性確保の方針、確認方法）

tasks.md フェーズ3
  → 「リグレッションテスト」として実行（影響範囲で特定したリスク箇所を対象に含める）
```

requirements.mdで影響範囲が「なし」と判断された場合でも、design.mdの§10.2で「既存機能への影響なし」と明記すること。
