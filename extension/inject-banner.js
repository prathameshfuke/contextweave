(async () => {
  const { lastCapture, activeProject } = await chrome.storage.local.get(['lastCapture', 'activeProject']);
  if (!lastCapture) return;

  const ago = Math.round((Date.now() - lastCapture.timestamp) / 60000);
  const tokens = Math.round(lastCapture.markdown.length / 4);

  const banner = document.createElement('div');
  banner.id = 'cw-banner';
  banner.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    background: #2a2560;
    color: white;
    z-index: 999999;
    padding: 10px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: sans-serif;
    font-size: 14px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    transform: translateY(-100%);
    transition: transform 0.3s ease-out;
  `;

  banner.innerHTML = `
    <div>
      <strong>ContextWeave</strong> • Context available: ${activeProject} 
      <span style="opacity: 0.8; margin-left: 10px;">Captured ${ago} min ago • ~${tokens} tokens</span>
    </div>
    <div>
      <button id="cw-inject" style="background: #7F77DD; border: none; color: white; padding: 5px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-right: 10px;">Inject into this chat</button>
      <button id="cw-dismiss" style="background: transparent; border: 1px solid white; color: white; padding: 5px 15px; border-radius: 4px; cursor: pointer;">Dismiss</button>
    </div>
  `;

  document.body.appendChild(banner);
  setTimeout(() => banner.style.transform = 'translateY(0)', 100);

  document.getElementById('cw-dismiss').onclick = () => {
    banner.style.transform = 'translateY(-100%)';
    setTimeout(() => banner.remove(), 300);
    chrome.storage.local.set({ bannerDismissed: true });
  };

  document.getElementById('cw-inject').onclick = () => {
    const host = window.location.hostname;
    let selector = '';
    if (host.includes('claude.ai')) selector = 'div[contenteditable="true"]';
    else if (host.includes('chatgpt.com')) selector = 'div#prompt-textarea';
    else if (host.includes('gemini.google.com')) selector = 'div.ql-editor';

    const input = document.querySelector(selector);
    if (input) {
      const contextText = `<context>\n${lastCapture.markdown}\n</context>\n\nContinue from where the previous session left off.`;
      
      if (input.tagName === 'DIV') {
        input.innerText = contextText;
      } else {
        input.value = contextText;
      }
      
      // Trigger input event
      input.dispatchEvent(new Event('input', { bubbles: true }));
      
      banner.style.transform = 'translateY(-100%)';
      setTimeout(() => banner.remove(), 300);
    } else {
      alert('Could not find chat input box.');
    }
  };
})();
