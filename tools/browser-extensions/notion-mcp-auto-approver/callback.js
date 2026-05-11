(() => {
  console.log('[notion-mcp-auto-approver] callback page loaded');

  const MAX_WAIT = 10000;
  const INTERVAL = 500;
  let elapsed = 0;

  function check() {
    if (document.body.textContent.includes('Invalid MCP state. Please enable browser cookies and try again.')) {
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
