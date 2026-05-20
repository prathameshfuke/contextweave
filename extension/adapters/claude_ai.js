(function registerClaudeAdapter(global) {
  const registry = global.ContextWeaveAdapters || (global.ContextWeaveAdapters = {});

  function orderedCandidates(root) {
    const userTurns = Array.from(root.querySelectorAll('[data-testid="user-message"]'));
    const assistantTurns = Array.from(root.querySelectorAll('div[data-is-streaming], .font-claude-response'));
    const seen = new Set();
    const items = [];

    const addItem = (el, role) => {
      if (!el || seen.has(el)) {
        return;
      }
      seen.add(el);
      items.push({ el, role, content: el.innerText.trim() });
    };

    userTurns.forEach((el) => addItem(el, 'user'));
    assistantTurns.forEach((el) => addItem(el, 'assistant'));

    items.sort((a, b) => {
      if (a.el === b.el) return 0;
      return a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });

    return items.map(({ role, content }) => ({ role, content }));
  }

  registry.claude = {
    extractTurns(root = document) {
      return orderedCandidates(root);
    }
  };
})(globalThis);
