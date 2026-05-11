# ファイル書き込み戦略ガイド

IDEのfs_write/fs_appendツールで大きなコンテンツを書き込む際の共通戦略。

---

## 推奨方式: fs_write + fs_append + str_replace 分割追記

1. `fs_write` でフロントマター（YAMLメタ情報 + 閉じ `---`）を書き込む（ファイル新規作成）
2. `str_replace` で閉じ `---` の直後に最初の本文セクションを挿入する
3. `fs_append` で残りの本文セクションを分割して追記する

**ルール:**
- 1回の書き込みあたり概ね2000文字以内に抑える
- 分割単位はセクション境界（`## `見出し）で区切る
- フロントマターが不要なファイルの場合は `fs_write` で先頭セクションを書き、`fs_append` で残りを追記する

## 禁止事項（シェルのクォート問題でハングする）

- heredoc (`<< 'EOF'`) でのコンテンツ渡し
- `echo` への長文直接渡し
- `python3.12 -c` に長い文字列リテラルを渡す

## 失敗判定と切り替え

- `fs_write` / `fs_append` が「text パラメータが undefined」エラーで失敗した場合 → チャンクをさらに小さく分割して再試行（1000文字以内）
- 2回連続で同じツールが失敗した場合 → フォールバック方式に切り替え

## フォールバック（fs_write/fs_append が繰り返し失敗する場合）

`~/scripts/encode-to-b64.py` + `~/scripts/decode-b64-write.py` を使用する。
手順:
1. `fs_write` で一時ファイル（例: `/tmp/chunk-src.md`）にチャンクを書く（短いチャンクなら成功する）
2. `python3.12 ~/scripts/encode-to-b64.py /tmp/chunk-src.md` でBase64化
3. `cat /tmp/chunk.b64 | python3.12 ~/scripts/decode-b64-write.py {ターゲットパス} --append` で書き込み

この方式はBase64経由のため、シングルクォート・ダブルクォート・バッククォート・トリプルクォート・$変数展開等あらゆる特殊文字に対応する。
