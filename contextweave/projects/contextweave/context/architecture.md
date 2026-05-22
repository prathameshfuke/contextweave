# Architecture: ContextWeave

## System Layers
1. **AI Agent Adapters:** Claude Code, Gemini CLI, etc.
2. **Context Engine:** Python library for session management.
3. **Obsidian Vault:** The knowledge graph and storage layer.
4. **Chrome Extension:** ContextWeave Clipper for web research.

## Data Flow
Agents read from and write to the vault via the Context Engine. The engine uses the Obsidian Local REST API and direct file system access.
