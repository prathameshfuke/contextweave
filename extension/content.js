const PAGE_READY_TIMEOUT_MS = 10000;

function waitForDomReady() {
  if (document.readyState !== 'loading') {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    document.addEventListener('DOMContentLoaded', () => resolve(), { once: true });
  });
}

function waitForSelector(selector, timeoutMs = PAGE_READY_TIMEOUT_MS) {
  if (document.querySelector(selector)) {
    return Promise.resolve(document.querySelector(selector));
  }

  return new Promise((resolve, reject) => {
    const started = Date.now();
    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        resolve(el);
      } else if (Date.now() - started > timeoutMs) {
        observer.disconnect();
        reject(new Error(`Timed out waiting for ${selector}`));
      }
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      const el = document.querySelector(selector);
      if (el) {
        resolve(el);
      } else {
        reject(new Error(`Timed out waiting for ${selector}`));
      }
    }, timeoutMs);
  });
}

function getAdapter() {
  const host = window.location.hostname;
  const adapters = globalThis.ContextWeaveAdapters || {};

  if (host.includes('claude.ai')) {
    return adapters.claude;
  }
  if (host.includes('chatgpt.com')) {
    return adapters.chatgpt;
  }
  if (host.includes('gemini.google.com')) {
    return adapters.gemini;
  }
  return null;
}

function getTurnSelector() {
  const host = window.location.hostname;
  if (host.includes('claude.ai')) {
    return '[data-testid="user-message"], div[data-is-streaming], .font-claude-response';
  }
  if (host.includes('chatgpt.com')) {
    return '[data-message-author-role]';
  }
  if (host.includes('gemini.google.com')) {
    return 'user-query, model-response';
  }
  return '';
}

function getComposerSelector() {
  const host = window.location.hostname;
  if (host.includes('claude.ai')) {
    return '[contenteditable="true"][role="textbox"], [contenteditable="true"]';
  }
  if (host.includes('chatgpt.com')) {
    return '#prompt-textarea, textarea';
  }
  if (host.includes('gemini.google.com')) {
    return 'textarea, [contenteditable="true"]';
  }
  return '';
}

function buildClipMarkdown(mode) {
  const title = document.title.trim() || window.location.hostname;
  const source = window.location.href;
  const selection = window.getSelection()?.toString().trim() || '';
  const bodyText = document.body ? document.body.innerText.trim() : '';

  let content = bodyText;
  if (mode === 'selection' && selection) {
    content = selection;
  } else if (mode === 'summary') {
    content = selection || bodyText.slice(0, 4000);
  }

  return `---\nsource: ${source}\ntitle: ${title}\ncaptured: ${new Date().toISOString()}\n---\n\n# ${title}\n\n${content}`;
}

async function handleCapture() {
  await waitForDomReady();
  const adapter = getAdapter();
  if (!adapter || typeof adapter.extractTurns !== 'function') {
    return { turns: [], raw: '' };
  }

  const selector = getTurnSelector();
  if (selector) {
    try {
      await waitForSelector(selector);
    } catch (_) {
      // Fall back to whatever is currently available.
    }
  }

  const turns = adapter.extractTurns(document);
  const raw = turns.map((t) => `${t.role === 'user' ? 'User' : 'Assistant'}: ${t.content}`).join('\n\n');
  return { turns, raw };
}

async function handleClip(request) {
  await waitForDomReady();

  if (request.mode === 'selection') {
    const selected = window.getSelection()?.toString().trim();
    if (selected) {
      return { markdown: buildClipMarkdown('selection') };
    }
  }

  return { markdown: buildClipMarkdown(request.mode || 'full') };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'capture') {
    handleCapture()
      .then(sendResponse)
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }

  if (request.action === 'getTurnCount') {
    handleCapture()
      .then((resp) => sendResponse({ count: resp.turns.length }))
      .catch((error) => sendResponse({ count: 0, error: error.message }));
    return true;
  }

  if (request.action === 'clip') {
    handleClip(request)
      .then(sendResponse)
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
});
