export function extractTurns() {
  const turns = [];
  // Human turns
  document.querySelectorAll('[data-testid="human-turn"]').forEach(el => {
    turns.push({ role: "user", content: el.innerText.trim() });
  });
  // Assistant turns — interleave by DOM order
  const allTurns = document.querySelectorAll('[data-testid="human-turn"], [data-testid="assistant-turn"]');
  const ordered = [];
  allTurns.forEach(el => {
    const role = el.dataset.testid === "human-turn" ? "user" : "assistant";
    ordered.push({ role, content: el.innerText.trim() });
  });
  return ordered;
}
