#!/usr/bin/env python3.12
"""
encode-to-b64: ファイルをBase64エンコードして /tmp/chunk.b64 に出力する

いつ使うか:
    AIエージェントがfs_write/fs_appendツールで大きなコンテンツの書き込みに
    繰り返し失敗する場合のフォールバック手段。
    通常はfs_write + fs_append の分割追記（1回2000文字以内）で十分。
    それでも失敗する場合にのみ、このスクリプトを使用する。

使い方:
    # 1. fs_write で一時ファイルにコンテンツを書く（短いチャンクなら成功する）
    #    例: fs_write で /tmp/chunk-src.md を作成

    # 2. このスクリプトでBase64化
    python3.12 ~/scripts/encode-to-b64.py /tmp/chunk-src.md

    # 3. decode-b64-write.py でターゲットに書き込み
    cat /tmp/chunk.b64 | python3.12 ~/scripts/decode-b64-write.py path/to/target.md --append

    # 出力先を変更する場合
    python3.12 ~/scripts/encode-to-b64.py /tmp/chunk-src.md --out /tmp/other.b64

前提:
    - decode-b64-write.py と組み合わせて使う
    - ソースファイルが存在すること
"""
import sys, base64, pathlib

args = sys.argv[1:]
if not args or args[0] in ("-h", "--help"):
    print(__doc__.strip())
    sys.exit(0)

source = pathlib.Path(args[0]).expanduser()
out = pathlib.Path("/tmp/chunk.b64")

if "--out" in args:
    idx = args.index("--out")
    out = pathlib.Path(args[idx + 1]).expanduser()

if not source.exists():
    print(f"Error: {source} not found", file=sys.stderr)
    sys.exit(1)

data = source.read_bytes()
out.write_text(base64.b64encode(data).decode())
print(f"encoded: {source} -> {out} ({len(data)} bytes)")
