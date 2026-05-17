---
inclusion: always
description: fileMatch steeringが自動インクルードされない場合のフォールバック。対象ファイルを扱う際に該当ルールのreadFileを促す
---

# fileMatch Steering ディスパッチャー

以下の条件に該当するファイルを扱う場合（読み込み・編集・作成）、対応するsteeringファイルをreadFileで読み込み、その指示に従うこと。

| 条件 | 読み込み対象 |
|------|-------------|
| `.zshrc` / `.bashrc` / `.shared-ai/prompts/*.md` を扱う場合 | `~/.kiro/steering/env-sync.md` |
| `**/*.py` を扱う場合 | `~/.kiro/steering/py-standards.md` |
| `scripts/*.py` を扱う場合 | `~/.kiro/steering/script-first-rule.md` |
| `**/*.sh` を扱う場合 | `~/.kiro/steering/sh-standards.md` |
| `.kiro/specs/**/design.md` を扱う場合 | `~/.kiro/steering/design-format.md` |
| `.kiro/specs/**/requirements.md` を扱う場合 | `~/.kiro/steering/req-format.md` |
| `.kiro/specs/**/tasks.md` を扱う場合 | `~/.kiro/steering/tasks-format.md`, `~/.kiro/steering/spec-completion.md` |
| `.kiro/specs/**/*.md` を扱う場合 | `~/.kiro/steering/spec-frontmatter.md` |
| `.kiro/steering/*.md` を扱う場合 | `~/.kiro/steering/steering-ref.md` |
| `.kiro/**/*.{md,json,hook}` を扱う場合 | `~/.kiro/steering/kiro-arch.md` |
| `docs/domain/**/*.md` を扱う場合 | `~/.kiro/steering/domain-frontmatter.md` |
| `.shared-ai/references/*-guide.md` を扱う場合 | `~/.kiro/steering/ref-format.md` |
| `.shared-ai/prompts/*.md` を扱う場合 | `~/.kiro/steering/prompt-editing.md` |
| `**/scripts/run-*-pipeline.py` を扱う場合 | `~/.kiro/steering/pipeline-run-script.md` |
| `tests/**/*Test.php` を扱う場合 | `~/.kiro/steering/test-db-guard.md` |
| `works/poc-something/**/SUMMARY.md` を扱う場合 | `~/.kiro/steering/poc-writer.md` |
