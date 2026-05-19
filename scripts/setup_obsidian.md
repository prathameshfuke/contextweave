# Obsidian Setup Guide for ContextWeave

ContextWeave relies on your local Obsidian vault to store project metadata, handoff notes, and AI session logs. To communicate with the vault automatically, it uses the **Local REST API** plugin for Obsidian.

## Step 1: Install the Plugin
1. Open Obsidian.
2. Go to **Settings > Community Plugins**.
3. Turn off "Safe Mode" if it is currently on.
4. Click **Browse** and search for **Local REST API**.
5. Click **Install**, then click **Enable**.

## Step 2: Configure the Plugin
1. Go to the **Local REST API** settings in Obsidian.
2. The default port is usually `27123`. Ensure it matches the port expected by ContextWeave (also `27123`).
3. You will need your API key for the Chrome Extension. In the plugin settings, copy the **API Key** (Bearer token).
4. **Note:** ContextWeave CLI doesn't strictly need the API key to read files locally because it reads them from the file system, but the Chrome Extension needs it to inject clips and captures securely.

## Step 3: Configure Chrome Extension
1. Open the ContextWeave Chrome Extension popup.
2. Click the gear icon ⚙️ to open Settings.
3. Paste the **API Key** you copied from Obsidian.
4. Ensure the port is `27123`.
5. Save settings.

## Step 4: Verify Connection
Run the following command in your terminal:
```bash
contextweave doctor
```
You should see: `✓ Obsidian Local REST API reachable`

Your vault is now ready to serve as the local knowledge graph for ContextWeave!
