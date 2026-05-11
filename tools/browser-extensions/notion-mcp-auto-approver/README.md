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

### 2. 無効なコールバックタブの自動クローズ

対象: `https://mcp.notion.com/callback*`

ページに「Invalid MCP state. Please enable browser cookies and try again.」が表示された場合:

1. テキストが表示されるまでポーリング（500ms間隔、最大10秒）
2. 検知後1秒待機
3. タブを自動クローズ

## ファイル構成

| ファイル | 役割 |
|---|---|
| `manifest.json` | 拡張機能定義（Manifest V3） |
| `content.js` | インテグレーション承認ページの自動操作 |
| `callback.js` | コールバックページのエラー検知・タブクローズ |
| `background.js` | Service Worker（タブクローズAPI呼び出し） |
