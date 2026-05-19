(function() {
  if (document.getElementById('contextweave-inject-banner')) return;

  const banner = document.createElement('div');
  banner.id = 'contextweave-inject-banner';
  banner.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    background-color: #2a2560;
    color: white;
    z-index: 99999;
    padding: 10px;
    font-family: sans-serif;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    transform: translateY(-100%);
    transition: transform 0.3s ease-out;
  `;

  chrome.storage.local.get(['lastCapture', 'activeProject'], (data) => {
    if (!data.lastCapture) return;
    const tokens = Math.round(data.lastCapture.markdown.length / 4);
    const ago = Math.round((Date.now() - data.lastCapture.timestamp) / 60000);

    banner.innerHTML = `
      <div>
        <strong>ContextWeave</strong> • Context available: ${data.activeProject}<br>
        <small>Captured ${ago} min ago • ~${tokens} tokens</small>
      </div>
      <div>
        <button id="cw-inject-btn" style="background:#7F77DD;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer;margin-right:10px;font-weight:bold;">Inject into this chat</button>
        <button id="cw-dismiss-btn" style="background:transparent;color:#ccc;border:none;cursor:pointer;text-decoration:underline;">Dismiss</button>
      </div>
    `;

    document.body.appendChild(banner);
    
    // Animate in
    setTimeout(() => { banner.style.transform = 'translateY(0)'; }, 100);

    document.getElementById('cw-dismiss-btn').onclick = () => {
      banner.style.transform = 'translateY(-100%)';
      setTimeout(() => banner.remove(), 300);
      chrome.storage.local.set({ bannerDismissed: true });
    };

    document.getElementById('cw-inject-btn').onclick = () => {
      const markdown = data.lastCapture.markdown;
      const injection = `<context>\n${markdown}\n</context>\n\nContinue from where the previous session left off.`;
      
      const host = window.location.hostname;
      let input;

      if (host.includes('claude.ai')) {
        input = document.querySelector('div[contenteditable="true"]');
        if (input) {
          input.focus();
          document.execCommand('insertText', false, injection);
        }
      } else if (host.includes('chatgpt.com')) {
        input = document.querySelector('div#prompt-textarea');
        if (input) {
          input.focus();
          document.execCommand('insertText', false, injection);
        }
      } else if (host.includes('gemini.google.com')) {
        input = document.querySelector('div.ql-editor');
        if (input) {
          input.focus();
          document.execCommand('insertText', false, injection);
        }
      }

      if (input) {
        banner.style.transform = 'translateY(-100%)';
        setTimeout(() => banner.remove(), 300);
        chrome.storage.local.set({ bannerDismissed: true });
      } else {
        alert("ContextWeave: Could not find the chat input box.");
      }
    };
  });
})();
