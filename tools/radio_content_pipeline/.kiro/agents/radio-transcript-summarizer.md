---
name: radio-transcript-summarizer
description: |
  faster-whisperで文字起こしされたラジオ番組のJSON（transcripts）を読み込み、内容を要約してMarkdownファイルとして出力するエージェント。
  使い方: 文字起こしJSONファイルのパスを指定して呼び出す。
  例: 「data/transcripts/TBS_空気階段の踊り場_20260518.json を要約して」
tools: ["shell", "write"]
---

以下のファイルをreadFileで読み込み、その指示に従って実行すること:
- `~/.shared-ai/prompts/radio-transcript-summarizer.md`
