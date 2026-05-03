---
inclusion: auto
description: ドメイン知識、実装パターン、AI指示の配置先ルールと、docs/domain/への集約方針を定義する
---

# ナレッジ管理ルール

プロジェクト内のドメイン知識、実装パターン、AIへの指示を適切な場所に配置するためのルール。

## 知識の分類と配置先

| 分類               | 配置先                          | 内容                                                           | ISO/IEC 14764 分類                                     | 例                                                                     |
| ------------------ | ------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------- |
| ドメイン知識       | `docs/domain/`                  | ビジネスルール、業務フロー、データモデル、ステートマシン       | Adaptive（適応）; Perfective（完全化）                 | 契約ステータスライフサイクル; 販売スキーム別仕様; 無償譲渡判定ロジック |
| 時点の実装仕様     | `.kiro/specs/*/requirements.md` | 特定機能の要件定義（凍結して履歴として残す）                   | 全分類（spec_typeで区別: feat/fix/refactor/perf/docs） | 買取画面の同期機能仕様; Amazon Connect管理画面仕様                     |
| AI指示・制約       | `.kiro/steering/`               | フォーマットガイド、記述規約、用語集                           | Preventive（予防）                                     | Requirementsフォーマット; 受入基準の記述規約                           |
| 実装パターン・規約 | `.claude/skills/` 等            | コーディング規約、フレームワーク固有のパターン、ツール操作手順 | Perfective（完全化）; Preventive（予防）               | Laravel-Admin実装パターン; マイグレーション規約; ログ運用              |

## 絶対ルール

### ドメイン知識は `docs/domain/` に集約する

- skill（`.claude/skills/`, `.agents/skills/` 等）にドメイン知識を記載しない
- steeringにドメイン知識を記載しない
- ドメイン知識が必要な場合は `docs/domain/` の該当ファイルを参照する

### skillに許可される内容

- 実装パターン・コーディング規約（例: Laravel-Adminの実装方法）
- ツール操作手順（例: dbhubの使い方）
- `docs/domain/` への参照リンク（ドメイン知識本体ではなく、参照先の案内）

### skillにドメイン知識が混入している場合の対処

1. ドメイン知識部分を `docs/domain/` の該当ファイルに移動
2. skill側は `docs/domain/` への参照に置き換え
3. 該当するドメインファイルがなければ新規作成

## `docs/domain/` ファイルのフォーマット

```yaml
---
domain: { ドメイン名 }
title: { タイトル }
status: active
created_at: { YYYY-MM-DD }
created_by: { 作成者 }
updated_at: { YYYY-MM-DD }
updated_by: { 更新者 }
related_specs:
  - { spec名 }
---
```

### 本文の構造

```markdown
# {タイトル}

## 概要

<!-- このドメインの目的と全体像を2-3文で -->

## ビジネスルール

<!-- 不変のビジネスルール。箇条書きで端的に -->

## データモデル

<!-- 主要なテーブル・モデルとリレーション -->

## 主要な処理フロー

<!-- ユースケースごとの処理フロー -->

## 変更履歴

| 日付         | 変更内容 | 関連spec | 更新者   |
| ------------ | -------- | -------- | -------- |
| {YYYY-MM-DD} | 初版作成 | -        | {作成者} |
```

## spec完了時のドメイン知識更新フロー

```
spec実装完了
  → requirements.md, design.md, tasks.md のstatusをfrozenに変更
  → 各ファイルのfront-matterの updated_at, updated_by を更新
  → docs/domain/ の該当ファイルに新しい仕様を反映
    → front-matterのupdated_at, updated_by, related_specsを更新
    → 変更履歴テーブルに行を追加
  → glossaryに新用語があれば追加
```

## プロジェクト固有の構造

`docs/domain/` のディレクトリ構造はプロジェクトごとに定義する。
プロジェクトの `.kiro/steering/knowledge-management-rules.md` で追加定義し、具体的なディレクトリ構造やskill移行状況を記載すること。
