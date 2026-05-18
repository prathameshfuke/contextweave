document.addEventListener('DOMContentLoaded', async () => {
  const projectDropdown = document.getElementById('project-dropdown');
  const addProjectBtn = document.getElementById('add-project-btn');
  const newProjectInput = document.getElementById('new-project-input');
  const chatSection = document.getElementById('chat-capture-section');
  const webSection = document.getElementById('web-clipper-section');
  const platformName = document.getElementById('platform-name');
  const turnsCount = document.getElementById('turns-count');
  const captureBtn = document.getElementById('capture-btn');
  const copyMdBtn = document.getElementById('copy-md-btn');
  const saveVaultBtn = document.getElementById('save-vault-btn');
  const clipBtn = document.getElementById('clip-btn');
  const clipMode = document.getElementById('clip-mode');
  const tagProjectName = document.getElementById('tag-project-name');
  const lastCaptureTime = document.getElementById('last-capture-time');
  const tokenEstimate = document.getElementById('token-estimate');
  const spinner = document.getElementById('spinner');
  const settingsToggle = document.getElementById('settings-toggle');
  const settingsPanel = document.getElementById('settings-panel');
  const obsidianApiKey = document.getElementById('obsidian-api-key');
  const obsidianPort = document.getElementById('obsidian-port');
  const ollamaModel = document.getElementById('ollama-model');
  const saveSettingsBtn = document.getElementById('save-settings');

  // Load storage
  let data = await chrome.storage.local.get({
    activeProject: 'default',
    projects: ['default'],
    lastCapture: null,
    obsidian_api_key: '',
    obsidian_port: '27123',
    ollama_model: 'mistral'
  });

  // Init projects
  const refreshProjects = () => {
    projectDropdown.innerHTML = '';
    data.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      if (p === data.activeProject) opt.selected = true;
      projectDropdown.appendChild(opt);
    });
    tagProjectName.textContent = data.activeProject;
  };
  refreshProjects();

  // Settings
  obsidianApiKey.value = data.obsidian_api_key;
  obsidianPort.value = data.obsidian_port;
  ollamaModel.value = data.ollama_model;

  settingsToggle.onclick = () => settingsPanel.classList.toggle('hidden');
  saveSettingsBtn.onclick = async () => {
    await chrome.storage.local.set({
      obsidian_api_key: obsidianApiKey.value,
      obsidian_port: obsidianPort.value,
      ollama_model: ollamaModel.value
    });
    settingsPanel.classList.add('hidden');
  };

  // Project selection
  projectDropdown.onchange = async () => {
    data.activeProject = projectDropdown.value;
    await chrome.storage.local.set({ activeProject: data.activeProject });
    tagProjectName.textContent = data.activeProject;
  };

  addProjectBtn.onclick = () => {
    addProjectBtn.classList.add('hidden');
    newProjectInput.classList.remove('hidden');
    newProjectInput.focus();
  };

  newProjectInput.onkeydown = async (e) => {
    if (e.key === 'Enter' && newProjectInput.value.trim()) {
      const slug = newProjectInput.value.trim();
      if (!data.projects.includes(slug)) {
        data.projects.push(slug);
      }
      data.activeProject = slug;
      await chrome.storage.local.set({
        projects: data.projects,
        activeProject: data.activeProject
      });
      newProjectInput.value = '';
      newProjectInput.classList.add('hidden');
      addProjectBtn.classList.remove('hidden');
      refreshProjects();
    }
  };

  // Detect Platform
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab.url;
  if (url.includes('claude.ai')) {
    platformName.textContent = 'Claude';
    chatSection.classList.remove('hidden');
  } else if (url.includes('chatgpt.com')) {
    platformName.textContent = 'ChatGPT';
    chatSection.classList.remove('hidden');
  } else if (url.includes('gemini.google.com')) {
    platformName.textContent = 'Gemini';
    chatSection.classList.remove('hidden');
  } else {
    webSection.classList.remove('hidden');
  }

  // Update Last Capture
  if (data.lastCapture) {
    const ago = Math.round((Date.now() - data.lastCapture.timestamp) / 60000);
    lastCaptureTime.textContent = ago < 1 ? 'just now' : `${ago} min ago`;
    tokenEstimate.textContent = `~${Math.round(data.lastCapture.markdown.length / 4)} tokens`;
    copyMdBtn.disabled = false;
    saveVaultBtn.disabled = false;
  }

  // Actions
  captureBtn.onclick = async () => {
    spinner.classList.remove('hidden');
    try {
      const response = await chrome.tabs.sendMessage(tab.id, { action: 'capture' });
      turnsCount.textContent = response.turns.length;
      
      const compressed = await chrome.runtime.sendMessage({
        action: 'compress',
        raw: response.raw
      });

      if (compressed.error) throw new Error(compressed.error);

      data.lastCapture = {
        markdown: compressed.markdown,
        timestamp: Date.now()
      };
      await chrome.storage.local.set({ lastCapture: data.lastCapture });

      tokenEstimate.textContent = `~${Math.round(compressed.markdown.length / 4)} tokens`;
      lastCaptureTime.textContent = 'just now';
      copyMdBtn.disabled = false;
      saveVaultBtn.disabled = false;
    } catch (e) {
      alert(e.message);
    } finally {
      spinner.classList.add('hidden');
    }
  };

  saveVaultBtn.onclick = async () => {
    spinner.classList.remove('hidden');
    const res = await chrome.runtime.sendMessage({
      action: 'saveToVault',
      markdown: data.lastCapture.markdown,
      project: data.activeProject,
      title: 'Chat Capture'
    });
    spinner.classList.add('hidden');
    if (res.success) {
      saveVaultBtn.textContent = 'Saved ✓';
      setTimeout(() => saveVaultBtn.textContent = 'Save to Vault', 2000);
    } else {
      alert(res.error);
    }
  };

  copyMdBtn.onclick = () => {
    navigator.clipboard.writeText(data.lastCapture.markdown);
    copyMdBtn.textContent = 'Copied ✓';
    setTimeout(() => copyMdBtn.textContent = 'Copy MD', 2000);
  };

  clipBtn.onclick = async () => {
    spinner.classList.remove('hidden');
    try {
      const response = await chrome.tabs.sendMessage(tab.id, {
        action: 'clip',
        mode: clipMode.value,
        activeProject: data.activeProject
      });
      
      const res = await chrome.runtime.sendMessage({
        action: 'saveToVault',
        markdown: response.markdown,
        project: data.activeProject,
        title: tab.title
      });

      if (res.success) {
        clipBtn.textContent = 'Clipped ✓';
        setTimeout(() => clipBtn.textContent = 'Clip this page', 2000);
      } else {
        throw new Error(res.error);
      }
    } catch (e) {
      alert(e.message);
    } finally {
      spinner.classList.add('hidden');
    }
  };
});
