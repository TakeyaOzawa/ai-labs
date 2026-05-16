# shared-logger-module: 共通ロガーモジュール新設

## 変更種別

refactor

## 概要

- パイプラインおよび各種ユーティリティスクリプトのログ出力処理を `scripts/logger.py` に集約する
- コンテキスト圧縮、フォーマット共通化、ログローテーション品質の均一化を実現する
- マルチプラットフォーム動作を前提とし、将来的なCloudWatch等クラウドサービスへの移行パスも確保する

## 問題・背景

### 現状の課題

1. **フォーマットの不統一**: 約40本のスクリプトが個別に `print(f"[{now_jst()}] ...")` を記述しており、タイムスタンプ形式・絵文字プレフィックス・インデントが微妙に異なる
2. **ログレベルの概念がない**: 全出力が `print()` で、DEBUG/INFO/WARNING/ERROR の区別がない。パイプライン実行時にノイズが多い
3. **ローテーションの分散管理**: `rotate_log()` が `_pipeline_common.py` にあるが、各スクリプトが個別に呼び出す必要がある
4. **構造化ログ未対応**: 現在はテキスト出力のみ。将来CloudWatch Logs等に送信する場合、JSON構造化ログへの変換が必要になる
5. **コンテキスト圧縮の余地**: 各スクリプトで繰り返されるログ出力パターンを共通化することで、AIエージェントのコンテキスト消費を削減できる

### 現在のログ出力パターン

```python
# パイプラインスクリプト（run-daily-pipeline.py, run-weekly-pipeline.py）
print(f"[{now_jst()}] 🔄 {entry_name} 実行中...")
print(f"[{now_jst()}]    ✅ {entry_name} 完了")
print(f"[{now_jst()}]    ❌ {entry_name} 失敗")

# エラーログ（_pipeline_common.py）
print(f"[{timestamp}] [{pipeline}] > [{agent}] {message}", file=sys.stderr)

# ユーティリティスクリプト（notify-slack.py等）
print(f"Error: {e}", file=sys.stderr)
```

## 方針

### 設計原則

1. **Python標準 `logging` モジュールをベースにする**（外部依存ゼロ）
2. **既存の出力フォーマット（タイムスタンプ+絵文字）を維持する**（移行時の視認性を損なわない）
3. **段階的移行を可能にする**（一括置換ではなく、スクリプト単位で順次移行）
4. **クラウド移行時はHandlerの差し替えのみで対応**（アプリケーションコード変更不要）

### アーキテクチャ

```
scripts/logger.py
├── get_logger(name)           # 名前付きロガー取得
├── PipelineFormatter          # [timestamp] emoji message 形式
├── JsonFormatter              # CloudWatch等向けJSON形式（将来用）
├── RotatingFileHandler拡張    # 既存rotate_log()互換のローテーション
└── setup_pipeline_logging()   # パイプライン用の一括セットアップ
```

### ログレベルと絵文字マッピング

| レベル | 絵文字 | 用途 |
|--------|--------|------|
| DEBUG | 🔍 | 詳細デバッグ情報（通常非表示） |
| INFO | 🔄/✅/📋 | 通常の進捗・完了報告 |
| WARNING | ⚠️ | 非致命的な問題（続行可能） |
| ERROR | ❌ | 処理失敗（該当タスクは中断） |
| CRITICAL | 🔴 | パイプライン全体の致命的エラー |

### マルチプラットフォーム対応

- タイムゾーン: `datetime.timezone` ベース（OS依存なし）
- ファイルパス: `pathlib.Path` 使用（既存規約準拠）
- ログファイルエンコーディング: UTF-8明示（Windows対応）
- 改行コード: `\n` 統一（`os.linesep` は使わない）
- ファイルロック: 不要（単一プロセス実行前提。将来マルチプロセス化時に `filelock` 追加を検討）

### クラウド移行パス（将来想定）

```
Phase 1（本issue）: ローカルファイル + コンソール出力（現状互換）
Phase 2: JsonFormatter追加 + 環境変数でフォーマッタ切替
Phase 3: CloudWatch Logs Handler追加（boto3依存、オプショナル）
Phase 4: 構造化ログにメトリクス埋め込み（実行時間、成功率等）
```

CloudWatch移行時の設計方針:
- `LOG_OUTPUT=cloudwatch` 環境変数でHandler切替
- boto3は遅延importで通常実行時のオーバーヘッドゼロ
- ログストリーム名: `{pipeline_name}/{date}/{agent_name}`
- バッチ送信（`PutLogEvents`）でAPI呼び出し回数を最小化

## 修正対象

### 新規作成

- `~/scripts/logger.py` — 共通ロガーモジュール

### 段階的移行対象（優先度順）

| 優先度 | ファイル | 理由 |
|--------|----------|------|
| P0 | `_pipeline_common.py` | 全パイプラインの基盤。`now_jst()`, `log_error()`, `rotate_log()` をlogger.pyに委譲 |
| P1 | `run-daily-pipeline.py` | 日次パイプライン本体 |
| P1 | `run-weekly-pipeline.py` | 週次パイプライン本体 |
| P2 | `run-academic-trend-scout-pipeline.py` | サブパイプライン |
| P2 | `run-gws-trend-scout-pipeline.py` | サブパイプライン |
| P2 | `run-github-org-trend-scout-pipeline.py` | サブパイプライン |
| P2 | `run-github-repo-analysis-pipeline.py` | サブパイプライン |
| P3 | `notify-slack.py` | 通知ユーティリティ |
| P3 | `fetch-rss-feeds.py` | RSS取得 |
| P3 | `fetch-slack-users.py` | Slackユーザー取得 |
| P3 | その他ユーティリティスクリプト（約30本） | 個別対応 |

## タスク分解

### Task 1: logger.py 基本実装

- **対象ファイル:** `~/scripts/logger.py`（新規）
- **変更内容:**
  - `get_logger(name: str, level: str = "INFO") -> logging.Logger` 関数
  - `PipelineFormatter` クラス（既存の `[timestamp] emoji message` 形式を再現）
  - `setup_pipeline_logging(name, log_dir, log_file, max_lines, keep_lines)` 関数
  - RotatingFileHandler互換のローテーション（既存 `rotate_log()` のロジックを内包）
  - 環境変数 `LOG_LEVEL` でレベル制御（デフォルト: INFO）
  - 環境変数 `LOG_FORMAT` でフォーマッタ切替（`text` / `json`、デフォルト: text）

### Task 2: _pipeline_common.py 統合

- **対象ファイル:** `~/scripts/_pipeline_common.py`
- **変更内容:**
  - `from logger import get_logger, setup_pipeline_logging` を追加
  - `now_jst()` は維持（他用途あり）、ログ出力時は logger 経由に変更
  - `log_error()` を logger.error() のラッパーに変更（後方互換シグネチャ維持）
  - `rotate_log()` は logger.py 側のHandler設定に委譲（既存呼び出し元は非推奨警告）

### Task 3: パイプラインスクリプト移行（P1）

- **対象ファイル:** `run-daily-pipeline.py`, `run-weekly-pipeline.py`
- **変更内容:**
  - `print(f"[{now_jst()}] ...")` → `logger.info(...)` に置換
  - 絵文字プレフィックスはFormatterが自動付与（コード側では不要に）
  - stderr出力は `logger.error()` に統一

### Task 4: サブパイプライン移行（P2）

- **対象ファイル:** `run-*-pipeline.py`（4本）
- **変更内容:** Task 3と同様のパターンで移行

### Task 5: ユーティリティスクリプト移行（P3）

- **対象ファイル:** `notify-slack.py`, `fetch-rss-feeds.py` 他
- **変更内容:** 各スクリプトの `print(..., file=sys.stderr)` を `logger.error/warning()` に置換

### Task 6: JsonFormatter実装（将来Phase 2準備）

- **対象ファイル:** `~/scripts/logger.py`
- **変更内容:**
  - `JsonFormatter` クラス追加（CloudWatch Logs互換のJSON出力）
  - `LOG_FORMAT=json` 時に自動切替
  - フィールド: `timestamp`, `level`, `pipeline`, `agent`, `message`, `extra`

## 影響範囲

- **直接影響**: `scripts/` 配下の全Pythonスクリプト（約40本）
- **間接影響**: launchd plist（StandardOutputPath/StandardErrorPathの出力形式が変わる可能性）
- **互換性**: 既存の `print()` 出力と視覚的に同一のフォーマットを維持するため、パイプライン実行結果の見た目は変わらない
- **破壊的変更なし**: `log_error()`, `rotate_log()`, `now_jst()` は後方互換シグネチャを維持

## 作業ボリューム見積もり

| タスク | 工数 | 備考 |
|--------|------|------|
| Task 1: logger.py基本実装 | 小 | 標準logging活用で100行程度 |
| Task 2: _pipeline_common.py統合 | 小 | 既存関数のラッパー化 |
| Task 3: P1パイプライン移行 | 中 | 2ファイル、各50箇所程度のprint置換 |
| Task 4: P2サブパイプライン移行 | 中 | 4ファイル |
| Task 5: P3ユーティリティ移行 | 大 | 約30ファイル（段階的に実施可） |
| Task 6: JsonFormatter | 小 | Phase 2準備。本体は50行程度 |

**合計**: Task 1〜3 で基盤完成（1セッション）、Task 4〜6 は段階的に実施

## テスト計画

- [ ] logger.py単体: `LOG_LEVEL=DEBUG` / `INFO` / `ERROR` でフィルタリングが正しく動作する
- [ ] logger.py単体: `LOG_FORMAT=json` でJSON出力が正しい形式になる
- [ ] パイプライン実行: 既存と同一の視覚的出力が得られる（回帰テスト）
- [ ] ログローテーション: 指定行数超過時に切り詰めが動作する
- [ ] マルチプラットフォーム: macOS + Linux（WSL2）で同一動作を確認
- [ ] launchd経由実行: StandardOutputPathへの出力が正常に行われる
- [ ] 後方互換: `log_error()`, `rotate_log()` の既存呼び出しが動作する
