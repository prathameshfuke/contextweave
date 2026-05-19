document.addEventListener('DOMContentLoaded', async () => {
  const projectDropdown = document.getElementById('project-dropdown');
  const showNewProjectBtn = document.getElementById('show-new-project');
  const newProjectInput = document.getElementById('new-project-input');
  const chatSection = document.getElementById('chat-capture');
  const webSection = document.getElementById('web-clipper');
  const platformName = document.getElementById('platform-name');
  const turnsCount = document.getElementById('turns-count');
  const captureBtn = document.getElementById('capture-btn');
  const postCapture = document.getElementById('post-capture');
  const copyMdBtn = document.getElementById('copy-md');
  const saveVaultBtn = document.getElementById('save-vault');
  const lastCaptureTime = document.getElementById('last-capture-time');
  const tokenEstimate = document.getElementById('token-estimate');
  const clipBtn = document.getElementById('clip-btn');
  const activeProjectName = document.getElementById('active-project-name');
  const settingsBtn = document.getElementById('settings-btn');
  const settingsPanel = document.getElementById('settings-panel');
  const apiKeyInput = document.getElementById('api-key');
  const ollamaModelInput = document.getElementById('ollama-model');
  const obsidianPortInput = document.getElementById('obsidian-port');
  const saveSettingsBtn = document.getElementById('save-settings');
  const statusMsg = document.getElementById('status-msg');

  // Load state
  let state = await chrome.storage.local.get({
    activeProject: '',
    projects: [],
    lastCapture: null,
    apiKey: '',
    ollamaModel: 'mistral',
    obsidianPort: '27123'
  });

  const updateProjectUI = () => {
    projectDropdown.innerHTML = '';
    state.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      if (p === state.activeProject) opt.selected = true;
      projectDropdown.appendChild(opt);
    });
    activeProjectName.textContent = state.activeProject || 'none';
  };

  updateProjectUI();
  apiKeyInput.value = state.apiKey;
  ollamaModelInput.value = state.ollamaModel;
  obsidianPortInput.value = state.obsidianPort;

  // Detect platform
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const isAI = /claude\.ai|chatgpt\.com|gemini\.google\.com/.test(tab.url);
  if (isAI) {
    chatSection.classList.remove('hidden');
    const platform = tab.url.includes('claude.ai') ? 'Claude' : 
                     tab.url.includes('chatgpt.com') ? 'ChatGPT' : 'Gemini';
    platformName.textContent = platform;
    
    // Ask content script for turn count
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { action: 'getTurnCount' });
      if (resp) turnsCount.textContent = resp.count;
    } catch (e) {}
  } else {
    webSection.classList.remove('hidden');
  }

  // Last capture info
  if (state.lastCapture) {
    const minAgo = Math.round((Date.now() - state.lastCapture.timestamp) / 60000);
    lastCaptureTime.textContent = minAgo === 0 ? 'just now' : `${minAgo} min ago`;
    tokenEstimate.textContent = `~${Math.round(state.lastCapture.markdown.length / 4)}`;
    postCapture.classList.remove('hidden');
  }

  // Events
  settingsBtn.onclick = () => settingsPanel.classList.toggle('hidden');
  
  saveSettingsBtn.onclick = async () => {
    state.apiKey = apiKeyInput.value;
    state.ollamaModel = ollamaModelInput.value;
    state.obsidianPort = obsidianPortInput.value;
    await chrome.storage.local.set({
      apiKey: state.apiKey,
      ollamaModel: state.ollamaModel,
      obsidianPort: state.obsidianPort
    });
    settingsPanel.classList.add('hidden');
    statusMsg.textContent = 'Settings saved';
    setTimeout(() => statusMsg.textContent = '', 2000);
  };

  projectDropdown.onchange = async () => {
    state.activeProject = projectDropdown.value;
    await chrome.storage.local.set({ activeProject: state.activeProject });
    activeProjectName.textContent = state.activeProject;
  };

  showNewProjectBtn.onclick = () => {
    showNewProjectBtn.classList.add('hidden');
    newProjectInput.classList.remove('hidden');
    newProjectInput.focus();
  };

  newProjectInput.onkeydown = async (e) => {
    if (e.key === 'Enter' && newProjectInput.value.trim()) {
      const slug = newProjectInput.value.trim();
      if (!state.projects.includes(slug)) {
        state.projects.push(slug);
      }
      state.activeProject = slug;
      await chrome.storage.local.set({
        projects: state.projects,
        activeProject: state.activeProject
      });
      newProjectInput.value = '';
      newProjectInput.classList.add('hidden');
      showNewProjectBtn.classList.remove('hidden');
      updateProjectUI();
    }
  };

  captureBtn.onclick = async () => {
    statusMsg.textContent = 'Capturing...';
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { action: 'capture' });
      turnsCount.textContent = resp.turns.length;
      
      statusMsg.textContent = 'Compressing...';
      const compressed = await chrome.runtime.sendMessage({
        action: 'compress',
        raw: resp.raw
      });

      if (compressed.error) throw new Error(compressed.error);

      state.lastCapture = {
        markdown: compressed.markdown,
        timestamp: Date.now()
      };
      await chrome.storage.local.set({ 
        lastCapture: state.lastCapture,
        bannerDismissed: false 
      });

      tokenEstimate.textContent = `~${Math.round(compressed.markdown.length / 4)}`;
      lastCaptureTime.textContent = 'just now';
      postCapture.classList.remove('hidden');
      statusMsg.textContent = 'Captured!';
    } catch (e) {
      statusMsg.textContent = 'Error: ' + e.message;
    }
  };

  copyMdBtn.onclick = () => {
    navigator.clipboard.writeText(state.lastCapture.markdown);
    statusMsg.textContent = 'Copied!';
    setTimeout(() => statusMsg.textContent = '', 2000);
  };

  saveVaultBtn.onclick = async () => {
    statusMsg.textContent = 'Saving...';
    const res = await chrome.runtime.sendMessage({
      action: 'saveToVault',
      markdown: state.lastCapture.markdown,
      project: state.activeProject
    });
    if (res.success) {
      statusMsg.textContent = 'Saved ✓';
    } else {
      statusMsg.textContent = 'Error: ' + res.error;
    }
  };

  clipBtn.onclick = async () => {
    statusMsg.textContent = 'Clipping...';
    const mode = document.querySelector('input[name="clip-mode"]:checked').value;
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { 
        action: 'clip', 
        mode,
        activeProject: state.activeProject 
      });
      
      const res = await chrome.runtime.sendMessage({
        action: 'saveToVault',
        markdown: resp.markdown,
        project: state.activeProject,
        filename: `${new Date().toISOString().split('T')[0]}-${tab.title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}.md`
      });

      if (res.success) {
        statusMsg.textContent = 'Clipped ✓';
      } else {
        throw new Error(res.error);
      }
    } catch (e) {
      statusMsg.textContent = 'Error: ' + e.message;
    }
  };
});
