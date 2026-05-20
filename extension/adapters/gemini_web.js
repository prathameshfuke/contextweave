(function registerGeminiAdapter(global) {
  const registry = global.ContextWeaveAdapters || (global.ContextWeaveAdapters = {});

  registry.gemini = {
    extractTurns(root = document) {
      return Array.from(root.querySelectorAll('user-query, model-response')).map((el) => ({
        role: el.tagName.toLowerCase() === 'user-query' ? 'user' : 'assistant',
        content: el.innerText.trim()
      }));
    }
  };
})(globalThis);
