export function extractTurns() {
  const ordered = [];
  document.querySelectorAll('user-query, model-response').forEach(el => {
    ordered.push({
      role: el.tagName.toLowerCase() === 'user-query' ? 'user' : 'assistant',
      content: el.innerText.trim()
    });
  });
  return ordered;
}
