# ContextWeave
> AI context persistence for multi-model developer workflows

ContextWeave solves the "context window amnesia" problem when working with AI coding assistants. Instead of repeatedly explaining your project, architectural decisions, and current state to different agents (Claude, ChatGPT, Gemini), ContextWeave captures, compresses, and injects your project's context automatically using a local Obsidian vault as a long-term knowledge graph.

## What it does
- **Continuous Memory**: Maintains an auto-updating graph of your project's decisions, handoffs, and in-progress tasks.
- **Cross-Agent Handoffs**: Allows Claude to seamlessly pick up a task exactly where Gemini left off.
- **Zero-Friction Injection**: Uses a Chrome extension to auto-inject the correct, compressed context into new AI chat sessions.
- **Local First**: Your source code, architecture notes, and chat captures live entirely locally in your Obsidian vault.
- **Semantic Retrieval**: Uses local vector search (ChromaDB + Ollama) to pull only the context relevant to your current feature.

## How it works
ContextWeave operates on a 4-layer architecture:

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │       │                 │
│  Obsidian Vault ├──────►│ ContextWeave CLI├──────►│ Chrome Ext      │
│  (Local Data)   │◄──────┤ (Engine)        │◄──────┤ (Web Clipper)   │
│                 │       │                 │       │                 │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │                         ▼                         │
         │                ┌─────────────────┐                │
         └───────────────►│  AI Adapters    │◄───────────────┘
                          │ (Claude/Gemini) │
                          └─────────────────┘
```

## Requirements
- Python 3.11+
- Ollama (free, local) with `mistral` or `llama3.2` model installed
- Obsidian with the **Local REST API** plugin
- Chrome or Chromium-based browser (for the extension)

## Install
```bash
git clone https://github.com/your-username/contextweave.git
cd contextweave
./scripts/install.sh
```
*Note: Make sure you configure your Obsidian vault and the Local REST API plugin according to `scripts/setup_obsidian.md` before using.*

## Quickstart
Go from zero to your first persistent session in 5 minutes:

1. `contextweave doctor` (Ensure your system is ready)
2. `contextweave init my-project` (Scaffolds the project in your vault)
3. `contextweave watch my-project` (Start the auto-indexer in a separate terminal)
4. `contextweave session start my-project --agent claude --feature "user auth"`
5. `contextweave inject my-project --adapter claude` (Injects context into `CLAUDE.md`)
6. When done, `contextweave session close my-project --summary "added JWT auth" --next "add login UI"`

## Commands
| Command | Description |
|---|---|
| `init <slug>` | Scaffolds a new project in your Obsidian vault. |
| `status <slug>` | Shows current state, last session, and pending tasks. |
| `watch [slug]` | Runs a file watcher to auto-index new vault notes. |
| `brief <slug>` | Generates a daily brief summarizing recent AI work. |
| `diff <slug>` | Shows the context delta between the last two sessions. |
| `session start` | Begins a new AI tracking session. |
| `session close` | Completes the session and generates a handoff note. |
| `inject <slug>` | Injects context into specific AI system prompt files. |
| `doctor` | Diagnoses your local setup (Ollama, Vault, API). |

## Chrome Extension
The included Chrome Extension brings ContextWeave directly into your browser workflow.
1. Go to `chrome://extensions/`
2. Enable **Developer Mode**.
3. Click **Load unpacked** and select the `extension/` folder.

**Features:**
- **Capture Chat**: Automatically pulls chat transcripts from Claude, ChatGPT, or Gemini and compresses them using local Ollama.
- **Web Clipper**: Save any documentation or web page directly to your active project in Obsidian.
- **Auto-Injection**: Opening a new AI chat automatically drops a floating banner to inject your most recent context seamlessly.

## Project vault structure
Inside your selected Obsidian vault, ContextWeave maintains:
```text
projects/
  └── my-project/
      ├── context/
      │   └── in-progress.md
      ├── sessions/
      │   └── 2026-05-19-claude-auth.md
      ├── agents/
      │   └── 2026-05-19-handoff.md
      └── web-captures/
          └── 2026-05-19-react-docs.md
```

## Free stack
ContextWeave is designed to operate with **zero API costs**.
- **Vector Search**: Local `all-MiniLM-L6-v2` via `sentence-transformers` and `ChromaDB`.
- **Summarization & Diffing**: Uses `Ollama` running `mistral` by default. Everything runs on your hardware, preserving your privacy and saving costs.

## Contributing
Contributions are welcome! Please ensure you include tests for any new CLI commands or adapters.
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
MIT License
