(() => {
  const CHECKBOX_XPATH = '/html/body/div/div/div/div[1]/div/div[2]/div/div[8]/div/div[2]/div/input';
  const BUTTON_XPATH = '/html/body/div/div/div/div[1]/div/div[2]/div/div[9]/div[1]';

  function getByXPath(xpath) {
    return document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
  }

  console.log('[notion-mcp-auto-approver] content script loaded');

  const MAX_WAIT = 10000;
  const INTERVAL = 500;
  let elapsed = 0;

  function run() {
    const text = document.body.textContent;
    if (!text.includes('Connect with Notion MCP') && !text.includes('Notion MCPに接続')) {
      elapsed += INTERVAL;
      if (elapsed >= MAX_WAIT) {
        console.log('[notion-mcp-auto-approver] target text not found after timeout, skipping');
        return;
      }
      setTimeout(run, INTERVAL);
      return;
    }
    const checkbox = getByXPath(CHECKBOX_XPATH);
    if (!checkbox) {
      elapsed += INTERVAL;
      if (elapsed >= MAX_WAIT) {
        console.log('[notion-mcp-auto-approver] checkbox not found after timeout, skipping');
        return;
      }
      setTimeout(run, INTERVAL);
      return;
    }
    console.log('[notion-mcp-auto-approver] auto-approving...');
    if (!checkbox.checked) {
      checkbox.click();
    }
    setTimeout(() => {
      const button = getByXPath(BUTTON_XPATH);
      if (button) {
        button.focus();
        button.click();
      }
    }, 1500);
  }

  run();
})();
