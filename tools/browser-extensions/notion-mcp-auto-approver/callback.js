(() => {
  console.log('[notion-mcp-auto-approver] callback page loaded');

  const MAX_WAIT = 10000;
  const INTERVAL = 500;
  let elapsed = 0;

  function check() {
    const text = document.body.textContent;

    if (text.includes('Authorization successful!') && text.includes('You may close this window and return to the CLI.')) {
      console.log('[notion-mcp-auto-approver] authorization successful, closing tab in 3s');
      setTimeout(() => chrome.runtime.sendMessage({ action: 'closeTab' }), 3000);
      return;
    }

    if (text.includes('Invalid MCP state. Please enable browser cookies and try again.')) {
      console.log('[notion-mcp-auto-approver] invalid MCP state detected, closing tab in 1s');
      chrome.runtime.sendMessage({ action: 'closeTab' });
      return;
    }

    elapsed += INTERVAL;
    if (elapsed >= MAX_WAIT) {
      console.log('[notion-mcp-auto-approver] target text not found after timeout, skipping');
      return;
    }
    setTimeout(check, INTERVAL);
  }

  check();
})();
