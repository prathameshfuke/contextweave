chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'compress') {
    handleCompression(request.raw, sendResponse);
    return true; // async
  }
  if (request.action === 'saveToVault') {
    handleSaveToVault(request, sendResponse);
    return true; // async
  }
});

async function handleCompression(raw, sendResponse) {
  const { ollamaModel } = await chrome.storage.local.get({ ollamaModel: 'mistral' });
  
  const systemPrompt = "You are a context summariser for a software project. Be concise, structured, and technical. Output markdown only. Focus on key decisions, code changes, and pending tasks.";
  const prompt = `Please compress the following chat transcript into a concise technical summary:\n\n${raw}`;

  try {
    const response = await fetch('http://localhost:11434/api/generate', {
      method: 'POST',
      body: JSON.stringify({
        model: ollamaModel,
        stream: false,
        system: systemPrompt,
        prompt: prompt
      })
    });

    if (!response.ok) throw new Error('Ollama not responding');
    const data = await response.json();
    sendResponse({ markdown: data.response });
  } catch (e) {
    sendResponse({ error: "Ollama not running. Start with: OLLAMA_ORIGINS=* ollama serve" });
  }
}

async function handleSaveToVault(request, sendResponse) {
  const { apiKey, obsidianPort } = await chrome.storage.local.get({ apiKey: '', obsidianPort: '27123' });
  const { project, markdown, filename } = request;
  
  const safeFilename = filename || `${new Date().toISOString().split('T')[0]}-chat-capture.md`;
  const url = `http://localhost:${obsidianPort}/vault/projects/${project}/web-captures/${safeFilename}`;

  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'text/markdown'
      },
      body: markdown
    });

    if (response.ok) {
      sendResponse({ success: true, path: url });
    } else {
      const err = await response.text();
      sendResponse({ error: err || response.statusText });
    }
  } catch (e) {
    sendResponse({ error: e.message });
  }
}

// Inject banner on navigation
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && /claude\.ai|chatgpt\.com|gemini\.google\.com/.test(tab.url)) {
    const { lastCapture, bannerDismissed } = await chrome.storage.local.get(['lastCapture', 'bannerDismissed']);
    
    if (lastCapture && !bannerDismissed) {
      const ageHours = (Date.now() - lastCapture.timestamp) / 3600000;
      if (ageHours < 2) {
        chrome.scripting.executeScript({
          target: { tabId },
          files: ['inject-banner.js']
        });
      }
    }
  }
});
