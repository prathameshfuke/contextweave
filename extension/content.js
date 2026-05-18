chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'capture') {
    captureChat().then(sendResponse);
    return true;
  }
  if (request.action === 'clip') {
    clipPage(request).then(sendResponse);
    return true;
  }
});

async function captureChat() {
  let adapter;
  const host = window.location.hostname;

  if (host.includes('claude.ai')) {
    adapter = await import(chrome.runtime.getURL('adapters/claude_ai.js'));
  } else if (host.includes('chatgpt.com')) {
    adapter = await import(chrome.runtime.getURL('adapters/chatgpt.js'));
  } else if (host.includes('gemini.google.com')) {
    adapter = await import(chrome.runtime.getURL('adapters/gemini_web.js'));
  }

  if (!adapter) return { error: "Adapter not found" };

  const turns = adapter.extractTurns();
  const raw = turns.map(t => `${t.role === 'user' ? 'User' : 'Assistant'}: ${t.content}`).join('\n\n');

  return { turns, raw };
}

async function clipPage({ mode, activeProject }) {
  // We need to inject Readability and Turndown manually if not using a bundler
  // For this scaffold, we'll assume they are loaded or we use a dynamic import if available
  // Since it's an unpacked extension, we can try to inject them or just read them from lib
  
  // Note: Standard content scripts don't have access to the 'lib' folder easily via import
  // We'll use a hack to load them or assume they are in the manifest (easier)
  
  // Actually, I'll update manifest.json to include them in content_scripts for simplicity
  
  const article = new Readability(document.cloneNode(true)).parse();
  const turndownService = new TurndownService();
  
  let content = article.content;
  if (mode === 'selection') {
    const selection = window.getSelection().toString();
    if (selection) content = selection;
  }
  
  let markdown = turndownService.turndown(content);

  if (mode === 'summary') {
    markdown = article.excerpt || markdown.slice(0, 500) + '...';
  }

  const frontmatter = `---
source: ${window.location.href}
title: ${article.title || document.title}
captured: ${new Date().toISOString()}
project: ${activeProject}
tags: []
---

# ${article.title || document.title}

${markdown}
`;

  return { markdown: frontmatter };
}
