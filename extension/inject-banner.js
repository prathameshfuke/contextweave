(async () => {
  const { lastCapture, activeProject } = await chrome.storage.local.get(['lastCapture', 'activeProject']);
  if (!lastCapture) {
    return;
  }

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
    box-sizing: border-box;
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
  setTimeout(() => {
    banner.style.transform = 'translateY(0)';
  }, 100);

  function insertText(target, text) {
    target.focus();

    if (target.isContentEditable) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(target);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);

      const inserted = document.execCommand('insertText', false, text);
      if (!inserted) {
        target.innerText = text;
      }

      target.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: text
      }));
      target.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true }));
      return;
    }

    target.value = text;
    target.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertText',
      data: text
    }));
    target.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true }));
  }

  document.getElementById('cw-dismiss').onclick = () => {
    banner.style.transform = 'translateY(-100%)';
    setTimeout(() => banner.remove(), 300);
    chrome.storage.local.set({ bannerDismissed: true });
  };

  document.getElementById('cw-inject').onclick = async () => {
    const host = window.location.hostname;
    const selectors = host.includes('claude.ai')
      ? ['[contenteditable="true"][role="textbox"]', '[contenteditable="true"]']
      : host.includes('chatgpt.com')
        ? ['#prompt-textarea', 'textarea']
        : ['textarea', '[contenteditable="true"]'];

    const input = selectors.map((selector) => document.querySelector(selector)).find(Boolean);

    if (!input) {
      alert('Could not find chat input box.');
      return;
    }

    const contextText = `<context>\n${lastCapture.markdown}\n</context>\n\nContinue from where the previous session left off.`;
    insertText(input, contextText);

    banner.style.transform = 'translateY(-100%)';
    setTimeout(() => banner.remove(), 300);
  };
})();
