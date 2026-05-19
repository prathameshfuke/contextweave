export function extractTurns() {
  const ordered = [];
  document.querySelectorAll('[data-message-author-role]').forEach(el => {
    ordered.push({
      role: el.dataset.messageAuthorRole,
      content: el.innerText.trim()
    });
  });
  return ordered;
}
