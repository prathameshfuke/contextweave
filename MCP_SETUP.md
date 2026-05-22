# MCP Setup Guide — ContextWeave

**Version:** 0.2.0  
**Port:** MCP (stdio) + Viewer (`:4222`)

---

## Quickstart — 4 Commands

```bash
pip install contextweave          # or: pip install -e . (from source)
contextweave init my-project
contextweave hooks install my-project
contextweave serve                # open localhost:4222
```

Then add the MCP config below to your editor and you're done.

---

## Environment Variable

Set `CONTEXTWEAVE_PROJECT` so hooks know which project to write to:

```bash
# Linux / macOS
export CONTEXTWEAVE_PROJECT=my-project

# Windows PowerShell
$env:CONTEXTWEAVE_PROJECT = "my-project"
```

Add to your shell profile or `.env` file to persist.

---

## Claude Code

Add to `~/.claude.json` or your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "contextweave": {
      "command": "contextweave-mcp",
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

**Or** with `python -m`:

```json
{
  "mcpServers": {
    "contextweave": {
      "command": "python",
      "args": ["-m", "contextweave.mcp_server"],
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

---

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)  
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "contextweave": {
      "command": "contextweave-mcp",
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

---

## Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "contextweave": {
      "command": "contextweave-mcp",
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

Also install hooks for Cursor hints:

```bash
contextweave hooks install my-project --all-agents
```

---

## Gemini CLI

Add to `~/.gemini/mcp_servers.json` or your project's `.gemini/mcp_servers.json`:

```json
{
  "contextweave": {
    "command": "contextweave-mcp",
    "env": {
      "CONTEXTWEAVE_PROJECT": "my-project"
    }
  }
}
```

---

## Cline (VS Code)

In VS Code settings or `.vscode/settings.json`:

```json
{
  "cline.mcpServers": {
    "contextweave": {
      "command": "contextweave-mcp",
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

---

## Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "contextweave": {
      "command": "contextweave-mcp",
      "args": [],
      "env": {
        "CONTEXTWEAVE_PROJECT": "my-project"
      }
    }
  }
}
```

---

## Roo Code

In Roo Code settings → MCP Servers → Add:

```json
{
  "name": "contextweave",
  "command": "contextweave-mcp",
  "env": {
    "CONTEXTWEAVE_PROJECT": "my-project"
  }
}
```

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `memory_observe` | Capture an observation/memory |
| `memory_search` | Hybrid BM25 + vector search |
| `memory_build_context` | Build full context block for system prompt injection |
| `memory_save` | Explicitly save a long-term memory |
| `memory_session_start` | Start a new agent session |
| `memory_session_close` | Close session + generate handoff |
| `memory_sessions` | List recent sessions |
| `memory_handoff_read` | Read the latest handoff |
| `memory_inject` | Inject context into CLAUDE.md / .cursorrules etc. |
| `memory_consolidate` | Run dedup + decay sweep |
| `memory_status` | Project status dashboard |
| `memory_graph_query` | Query knowledge graph |
| `memory_export` | Export to Obsidian vault |
| `memory_import_claude` | Import from Claude Code JSONL transcripts |
| `memory_brief` | Generate daily project brief |

---

## Hooks — Auto-capture for Claude Code

After `contextweave hooks install my-project`, the following hooks fire automatically:

| Hook Event | What It Captures |
|------------|-----------------|
| `SessionStart` | Session begins |
| `PreToolUse` | File tool invocations (Edit, Write, Read, Grep, Glob, Bash) |
| `PostToolUse` | Tool result preview (first 500 chars) |
| `PostToolFailure` | Tool errors |
| `SubagentStart` | Subagent spawned |
| `SubagentStop` | Subagent finished |
| `Stop` | Triggers consolidate + export |
| `SessionEnd` | Session terminates |
| `PreCompact` | Context window compaction triggered |

Hook scripts are written to `.claude/hooks/` and registered in `.claude/settings.json`.

---

## Web Viewer

```bash
contextweave serve          # opens http://localhost:4222
contextweave serve --port 8080  # custom port
```

**5 tabs:**
- **Graph** — D3 force-directed knowledge graph (drag, zoom, click-to-inspect)
- **Memories** — searchable observation list with source badges and decay bars
- **Sessions** — session timeline with agent icons and status pills
- **Stream** — live SSE feed of incoming observations, color-coded by source
- **Status** — stats dashboard + daily project brief

---

## Obsidian Vault Integration

Set vault path on project init:

```bash
contextweave init my-project --vault ~/Documents/MyVault
```

Or update existing project via config at `~/.contextweave/config.toml`:

```toml
vault_path = "/path/to/your/vault"
```

After each session, run:

```bash
contextweave export my-project
```

Or auto-export on every DB change:

```bash
contextweave watch my-project
```

Vault structure:
```
MyVault/
  projects/
    my-project/
      PROJECT.md          ← index with wikilinks
      GRAPH.md            ← top entities
      BRIEF-2026-05-22.md ← daily brief
      memories/
        1.md              ← individual memory files
        2.md
```

---

## Comparison with agentmemory

| Feature | agentmemory | contextweave |
|---------|-------------|--------------|
| Storage | JSON on disk via iii-engine | SQLite (ACID, WAL, FTS5) |
| Language | TypeScript/Node.js | Python (native ML ecosystem) |
| Embeddings | @xenova/transformers | sentence-transformers (no Ollama) |
| Search | BM25 + vector + graph | BM25 (FTS5) + vector (sqlite-vec) |
| MCP tools | 53 | 15 (focused, no bloat) |
| Setup | npm + iii-engine | pip install |
| LLM required | Yes (compression) | No (all features work offline) |
| Obsidian export | Add-on | First-class |
| Viewer | ✓ | ✓ (localhost:4222) |
| Claude Code hooks | 12 | 9 (matching event names) |
