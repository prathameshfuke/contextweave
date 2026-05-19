chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'capture') {
    handleCapture().then(sendResponse);
    return true;
  }
  if (request.action === 'getTurnCount') {
    handleCapture().then(resp => sendResponse({ count: resp.turns.length }));
    return true;
  }
  if (request.action === 'clip') {
    handleClip(request).then(sendResponse);
    return true;
  }
});

async function handleCapture() {
  const host = window.location.hostname;
  let adapter;
  
  if (host.includes('claude.ai')) {
    adapter = await import(chrome.runtime.getURL('adapters/claude_ai.js'));
  } else if (host.includes('chatgpt.com')) {
    adapter = await import(chrome.runtime.getURL('adapters/chatgpt.js'));
  } else if (host.includes('gemini.google.com')) {
    adapter = await import(chrome.runtime.getURL('adapters/gemini_web.js'));
  }

  if (!adapter) return { turns: [], raw: "" };

  const turns = adapter.extractTurns();
  const raw = turns.map(t => `${t.role === 'user' ? 'User' : 'Assistant'}: ${t.content}`).join('\n\n');
  return { turns, raw };
}

async function handleClip(request) {
  // We need to inject readability and turndown if not already present
  // But they are in lib/, we can't easily import them as modules if they aren't ES modules
  // Readability and Turndown usually aren't ES modules in their single-file builds
  
  // For this exercise, I'll assume I can use them via script injection or they are already loaded
  // Actually, content scripts can include them in manifest, but the user didn't ask for that.
  // Wait, the user said "load Readability.js (already in lib/)... run new Readability..."
  
  // I'll use a hack to load them if needed, or just hope they work.
  // Better: include them in manifest content_scripts? No, user provided manifest.
  
  // Actually, I can use dynamic import if I convert them to ES modules or if they are already.
  // Let's assume they are available in the global scope if I inject them.
  
  // To be safe, I'll fetch and eval them (not great, but works for an extension)
  if (typeof Readability === 'undefined') {
    const src = await (await fetch(chrome.runtime.getURL('lib/readability.js'))).text();
    eval(src);
  }
  if (typeof TurndownService === 'undefined') {
    const src = await (await fetch(chrome.runtime.getURL('lib/turndown.js'))).text();
    eval(src);
  }

  const documentClone = document.cloneNode(true);
  const article = new Readability(documentClone).parse();
  const turndownService = new TurndownService();
  const markdownBody = turndownService.turndown(article.content);

  const frontmatter = `---
source: ${window.location.href}
title: ${article.title}
captured: ${new Date().toISOString()}
project: ${request.activeProject}
tags: []
---

`;

  return { markdown: frontmatter + markdownBody };
}
