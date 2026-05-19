export function extractTurns() {
  const turns = [];
  const allTurns = document.querySelectorAll('[data-testid="human-turn"], [data-testid="assistant-turn"]');
  allTurns.forEach(el => {
    const role = el.dataset.testid === "human-turn" ? "user" : "assistant";
    turns.push({ role, content: el.innerText.trim() });
  });
  return turns;
}
