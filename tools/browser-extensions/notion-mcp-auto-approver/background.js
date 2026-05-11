chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.action === 'closeTab' && sender.tab) {
    setTimeout(() => chrome.tabs.remove(sender.tab.id), 1000);
  }
});
