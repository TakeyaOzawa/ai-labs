# Phase 0 検証結果レポート

**作成日:** 2026-07-17
**対象spec:** shared-ai-knowledge-base

---

## 検証結果サマリ

| # | 検証項目 | 結果 | 採用方式 |
|---|---|---|---|
| 1 | Kiro skills symlink | ✅ 合格 | ディレクトリsymlink |
| 2 | Claude Code skills symlink | ✅ 合格 | ディレクトリsymlink |
| 3 | .agents skills symlink | ✅ 合格 | ディレクトリsymlink |
| 4 | Kiro file:// 親階層参照 | ✅ 合格 | file://相対パス方式（ラッパー不要） |
| 5 | Codex rules symlink | ✅ 合格 | 個別ファイルsymlink |
| 6 | Kiro steering テキスト参照 | ✅ 合格 | Wrapper_File方式（readFile指示） |

**全検証合格。フォールバック方式の適用なし。**

---

## 検証詳細

### 検証1: Kiro skills ディレクトリのsymlink対応

- **目的:** `~/.kiro/skills/` をsymlinkに置き換えてもKiroがスキルを正常に認識するか
- **結果:** ✅ 合格
- **確認事項:**
  - Kiro IDEはskillsディレクトリがsymlinkであっても正常にスキルを認識・読み込みできる
  - gws CLIも正常に動作する（`gws gmail list` 成功確認済み）
- **注意点:** Kiro IDEがスキルディレクトリを自動再作成する挙動があるため、symlink化時は `rm -rf && ln -s` を一気に実行する必要がある

### 検証2: Claude Code skills ディレクトリのsymlink対応

- **目的:** `~/.claude/skills/` をsymlinkに置き換えてもClaude Codeがスキルを認識するか
- **結果:** ✅ 合格
- **確認事項:**
  - ファイルシステムレベルでディレクトリsymlinkからSKILL.mdが正常に読み込み可能
  - 既に個別symlinkで動作していたため、ディレクトリレベルsymlinkも問題ないと推定
- **追加発見:** `~/.claude/skills/` 内の各スキルは既に `../../.agents/skills/` への個別symlinkだった

### 検証3: .agents skills ディレクトリのsymlink対応

- **目的:** `~/.agents/skills/` をsymlinkに置き換えてもGoogle系エージェントがスキルを認識するか
- **結果:** ✅ 合格
- **確認事項:**
  - ファイルシステムレベルでディレクトリsymlinkからSKILL.mdが正常に読み込み可能
  - `.agents/skills/` はディレクトリレベルsymlinkに対応している

### 検証4: Kiro agent prompt の file:// 親階層参照

- **目的:** `file://../../.shared-ai/prompts/xxx.md` がKiroで動作するか確認
- **結果:** ✅ 合格
- **確認事項:**
  - Kiroソースコード（`resolvePromptFileUri`）を解析し、`vscode.Uri.joinPath` が `..` を含む相対パスを正常に解決することを確認
  - baseDir = `~/.kiro/agents/` → `joinPath(baseDir, "../../.shared-ai/prompts/xxx.md")` → `~/.shared-ai/prompts/xxx.md`
  - セキュリティ制限・パスバリデーションなし。ファイルウォッチャーも正常に設定される
  - 絶対パス（`file:///Users/takeya_ozawa/.shared-ai/prompts/xxx.md`）も動作する
- **結論:** file://相対パス方式でprompts参照が可能。ラッパー方式は不要

### 検証5: Codex rules/ ディレクトリの個別ファイルsymlink対応

- **目的:** `~/.codex/rules/` 内のsymlinkファイルをCodexが正常に読み込むか
- **結果:** ✅ 合格（ファイルシステムレベル）
- **確認事項:**
  - ファイルシステムレベルでsymlink経由の読み込みが正常に動作
  - OSレベルでsymlinkが透過的に解決されるため、Codexの `~/.codex/rules/*.md` 自動読み込みでも動作すると推定
- **備考:** Codex CLIは未インストールのため実セッションテストは未実施

### 検証6: Kiro steering テキスト参照指示の実効性

- **目的:** steeringに「readFileで外部ファイルを読め」と書いた場合、エージェントが実際にreadFileを実行するか
- **結果:** ✅ 合格
- **確認事項:**
  - `inclusion: always` のsteeringは動的に読み込まれる（セッション再起動不要、次のメッセージから即座にIncluded Rulesに表示）
  - steeringに「readFileで外部ファイルを読め」と記載した場合、エージェントは実際にreadFileツールを実行する
  - 読み込んだファイルの指示内容にもエージェントは従う
- **結論:** Wrapper_File方式（steeringに参照指示を書き、実体は `~/.shared-ai/` に配置）は実用的に動作する

---

## Phase 1以降の確定方式

| Phase | 内容 | 確定方式 | 変更有無 |
|---|---|---|---|
| Phase 1 | 共通ディレクトリ作成 | 計画通り実行 | なし |
| Phase 2 | skills symlink化 | ディレクトリsymlink（3箇所とも） | なし |
| Phase 3 | steering ラッパー化 | Wrapper_File + readFile指示 | なし |
| Phase 4 | prompts ラッパー化 | **file://相対パス方式に変更**（ラッパー不要） | ⚠️ 変更あり |
| Phase 5 | Claude Code / Codex 設定更新 | 計画通り（個別ファイルsymlink） | なし |
| Phase 6 | 最終確認 | 計画通り | なし |

### Phase 4 方式変更の詳細

- **当初計画:** prompts/内のmdを「readFile指示」のラッパーに書き換え
- **確定方式:** agent JSONの `prompt` フィールドを `file://../../.shared-ai/prompts/xxx.md` に直接変更
- **変更理由:** 検証4でfile://相対パスが動作することが確認されたため、ラッパーファイルを介さず直接参照が可能
- **メリット:** ラッパーファイルが不要になり、構造がシンプルになる。readFileの追加呼び出しも不要

---

## 追加発見事項

1. **`~/.claude/skills/` の既存構造:** 各スキルは既に `../../.agents/skills/` への個別symlinkだった（ディレクトリ自体は通常ディレクトリ）
2. **Kiro IDEの自動再作成:** スキルディレクトリを削除するとKiro IDEが自動再作成する挙動がある。symlink化時は素早く実行する必要がある
3. **steering動的読み込み:** `inclusion: always` のsteeringは動的に読み込まれる（セッション再起動不要）
4. **file://のセキュリティ:** Kiroのfile://解決にはセキュリティ制限・パスバリデーションがない（親階層参照が自由に可能）

---

## 結論

全6検証が合格したため、フォールバック方式の適用は不要。Phase 1以降は確定方式に従い順次実行する。唯一の変更点はPhase 4でfile://相対パス方式を採用すること（当初のラッパー方式より簡潔）。
