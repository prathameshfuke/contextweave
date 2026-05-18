const OLLAMA_URL = 'http://localhost:11434';

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'compress') {
    compressChat(request.raw).then(sendResponse);
    return true; // async
  }
  if (request.action === 'saveToVault') {
    saveToVault(request).then(sendResponse);
    return true; // async
  }
});

async function compressChat(rawTranscript) {
  const settings = await chrome.storage.local.get(['ollama_model']);
  const model = settings.ollama_model || 'mistral';

  const instruction = `Convert this AI chat into a structured handoff document another AI can read to continue the work.
Include:
- Project/task being worked on (2 sentences max)
- Key decisions made (bullet list with reasoning)
- Current state: what is done, what is in progress
- Critical constraints or patterns to follow
- Exact next step (be specific, mention file names)
- Open questions
Output as markdown with these exact headers. Be ruthlessly concise.`;

  try {
    const res = await fetch(`${OLLAMA_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: model,
        stream: false,
        system: "You are a context summariser for a software project. Be concise, structured, and technical. Output markdown only.",
        prompt: `${instruction}\n\n${rawTranscript}`
      })
    });
    const data = await res.json();
    return { markdown: data.response };
  } catch (e) {
    return { error: "Ollama not running. Start with: OLLAMA_ORIGINS=* ollama serve" };
  }
}

async function saveToVault({ markdown, project, title }) {
  const settings = await chrome.storage.local.get(['obsidian_api_key', 'obsidian_port']);
  if (!settings.obsidian_api_key) return { error: "Missing Obsidian API Key in settings" };

  const port = settings.obsidian_port || '27123';
  const date = new Date().toISOString().split('T')[0];
  const slug = title.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 50);
  const filename = `${date}-${slug}.md`;
  const path = `projects/${project}/web-captures/${filename}`;

  try {
    const res = await fetch(`http://localhost:${port}/vault/${path}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${settings.obsidian_api_key}`,
        'Content-Type': 'text/markdown'
      },
      body: markdown
    });
    if (res.ok) return { success: true, path };
    return { error: `Obsidian API error: ${res.status}` };
  } catch (e) {
    return { error: "Obsidian Local REST API not reachable." };
  }
}

// Inject banner on navigation
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    const isAI = ['claude.ai', 'chatgpt.com', 'gemini.google.com'].some(d => tab.url.includes(d));
    if (isAI) {
      const data = await chrome.storage.local.get(['lastCapture', 'bannerDismissed']);
      if (data.lastCapture && !data.bannerDismissed) {
        const age = (Date.now() - data.lastCapture.timestamp) / 3600000;
        if (age < 2) {
          chrome.scripting.executeScript({
            target: { tabId },
            files: ['inject-banner.js']
          });
        }
      }
    }
  }
});
