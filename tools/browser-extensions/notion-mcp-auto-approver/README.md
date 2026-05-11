# Notion MCP Auto Approver

Notion MCP 連携時の承認フローを自動化するChrome拡張機能。

## インストール

1. Chrome で `chrome://extensions` を開く
2. 右上の「デベロッパーモード」を有効化
3. 「パッケージ化されていない拡張機能を読み込む」をクリック
4. このディレクトリを選択

## 動作

### 1. インテグレーション承認の自動化

対象: `https://www.notion.so/install-integration*`

ページに「Connect with Notion MCP」または「Notion MCPに接続」が含まれている場合に自動実行:

1. チェックボックスが表示されるまでポーリング（500ms間隔、最大10秒）
2. チェックボックスをクリック
3. 1秒待機
4. 「続行」ボタンをクリック

### 2. コールバックタブの自動クローズ

対象: `https://mcp.notion.com/callback*`, `http://localhost:9553/oauth/callback?code=*`

ページのテキストをポーリング（500ms間隔、最大10秒）し、以下のいずれかを検知した場合にタブを自動クローズ:

- **認証成功時**: 「Authorization successful! You may close this window and return to the CLI.」を検知 → 3秒後にクローズ
- **エラー時**: 「Invalid MCP state. Please enable browser cookies and try again.」を検知 → 1秒後にクローズ

## ファイル構成

| ファイル | 役割 |
|---|---|
| `manifest.json` | 拡張機能定義（Manifest V3） |
| `content.js` | インテグレーション承認ページの自動操作 |
| `callback.js` | コールバックページの認証成功/エラー検知・タブクローズ |
| `background.js` | Service Worker（タブクローズAPI呼び出し） |
