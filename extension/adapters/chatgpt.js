(function registerChatGPTAdapter(global) {
  const registry = global.ContextWeaveAdapters || (global.ContextWeaveAdapters = {});

  registry.chatgpt = {
    extractTurns(root = document) {
      return Array.from(root.querySelectorAll('[data-message-author-role]')).map((el) => ({
        role: el.dataset.messageAuthorRole === 'user' ? 'user' : 'assistant',
        content: el.innerText.trim()
      }));
    }
  };
})(globalThis);
