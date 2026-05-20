const OLLAMA_TIMEOUT_MS = 60000;

function encodePathSegment(segment) {
  return encodeURIComponent(String(segment ?? ''));
}

function buildSafeFilename(input, fallbackBase = 'chat-capture') {
  const base = String(input ?? fallbackBase).trim();
  const withoutExt = base.replace(/\.md$/i, '');
  const normalized = withoutExt
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-+/g, '-')
    .toLowerCase();

  const safeBase = normalized || fallbackBase;
  return `${safeBase.slice(0, 120)}.md`;
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = OLLAMA_TIMEOUT_MS, timeoutMessage = 'Request timed out') {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    return response;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(timeoutMessage);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'compress') {
    handleCompression(request.raw, sendResponse);
    return true;
  }
  if (request.action === 'saveToVault') {
    handleSaveToVault(request, sendResponse);
    return true;
  }
});

async function handleCompression(raw, sendResponse) {
  const { ollamaModel } = await chrome.storage.local.get({ ollamaModel: 'mistral' });

  const systemPrompt = [
    'You are a context summariser for a software project.',
    'Return markdown only.',
    'Use these exact headers:',
    '## Project / Task',
    '## Key Decisions',
    '## Current State',
    '## Critical Constraints',
    '## Exact Next Step',
    '## Open Questions'
  ].join(' ');

  const prompt = `Compress the following chat transcript into a concise technical handoff.\n\n${raw}`;

  try {
    const response = await fetchJsonWithTimeout(
      'http://localhost:11434/api/generate',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: ollamaModel,
          stream: false,
          system: systemPrompt,
          prompt
        })
      },
      OLLAMA_TIMEOUT_MS,
      'Ollama took longer than 60 seconds to respond. Try a smaller model or wait for the model to finish loading.'
    );

    if (!response.ok) {
      throw new Error(`Ollama returned ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    sendResponse({ markdown: data.response || '' });
  } catch (error) {
    const message = error.message || 'Unknown Ollama error';
    sendResponse({ error: `Ollama compression failed: ${message}` });
  }
}

async function handleSaveToVault(request, sendResponse) {
  const { apiKey, obsidianPort } = await chrome.storage.local.get({ apiKey: '', obsidianPort: '27123' });
  const { project, markdown, filename, title } = request;
  const safeProject = encodePathSegment(project || 'default');
  const safeFilename = encodePathSegment(buildSafeFilename(filename || title || 'chat-capture'));
  const url = `http://localhost:${obsidianPort}/vault/projects/${safeProject}/web-captures/${safeFilename}`;

  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'text/markdown; charset=utf-8'
      },
      body: markdown
    });

    if (response.ok) {
      sendResponse({ success: true, path: decodeURIComponent(url) });
      return;
    }

    const err = await response.text();
    sendResponse({
      error: err || `Obsidian REST API returned ${response.status} ${response.statusText}`
    });
  } catch (error) {
    sendResponse({ error: error.message });
  }
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && /claude\.ai|chatgpt\.com|gemini\.google\.com/.test(tab.url || '')) {
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
