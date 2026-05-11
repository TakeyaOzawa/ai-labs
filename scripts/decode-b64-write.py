#!/usr/bin/env python3.12
"""
decode-b64-write: Base64エンコードされたstdinをデコードしてファイルに書き込む

いつ使うか:
    AIエージェントがfs_write/fs_appendツールで大きなコンテンツの書き込みに
    繰り返し失敗する場合のフォールバック手段。
    通常はfs_write + fs_append の分割追記（1回2000文字以内）で十分。
    それでも失敗する場合にのみ、このスクリプトを使用する。

使い方:
    # 1. encode-to-b64.py でソースファイルをBase64化
    python3.12 ~/scripts/encode-to-b64.py /tmp/chunk-src.md

    # 2. Base64ファイルをパイプしてターゲットに書き込み（上書き）
    cat /tmp/chunk.b64 | python3.12 ~/scripts/decode-b64-write.py path/to/target.md

    # 3. 追記モード
    cat /tmp/chunk.b64 | python3.12 ~/scripts/decode-b64-write.py path/to/target.md --append

前提:
    - encode-to-b64.py と組み合わせて使う
    - stdinにBase64エンコード済み文字列を渡すこと
"""
import sys, base64, pathlib

mode = "w"
args = sys.argv[1:]
if "--append" in args:
    mode = "a"
    args.remove("--append")

target = pathlib.Path(args[0]).expanduser()
target.parent.mkdir(parents=True, exist_ok=True)

data = base64.b64decode(sys.stdin.read().strip()).decode("utf-8")
with target.open(mode, encoding="utf-8") as f:
    f.write(data)

print(f"{'appended' if mode == 'a' else 'written'}: {target} ({target.stat().st_size} bytes)")
