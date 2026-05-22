"""
mcp_server.py — 15 MCP tools for contextweave.

Uses FastMCP (python mcp library).
Tool naming follows the memory_* prefix convention (compatible with agentmemory).

Run with: contextweave-mcp  OR  python -m contextweave.mcp_server
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP  # type: ignore

mcp = FastMCP("ContextWeave")

# ---------------------------------------------------------------------------
# Helper — get default project from env
# ---------------------------------------------------------------------------
def _default_project() -> str:
    return os.environ.get("CONTEXTWEAVE_PROJECT", "default")


# ---------------------------------------------------------------------------
# memory_observe — capture a new observation
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_observe(
    project: str,
    content: str,
    source: str = "mcp",
    agent: Optional[str] = None,
    tags: str = "",
) -> str:
    """
    Capture a new observation/memory for the given project.
    Use this to save anything important you learn during a session:
    decisions, discoveries, file changes, errors resolved.

    Args:
        project: Project slug (e.g. 'my-app')
        content: The observation text to store
        source: Source identifier (default 'mcp')
        agent: Agent name (optional)
        tags: Comma-separated tags (optional)
    """
    from .memory import observe
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    obs_id = observe(project, content, source=source, agent=agent, tags=tag_list)
    return json.dumps({"observation_id": obs_id, "status": "captured"})


# ---------------------------------------------------------------------------
# memory_search — search observations
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_search(
    project: str,
    query: str,
    top_k: int = 10,
) -> str:
    """
    Search past observations for relevant context using hybrid BM25 + vector search.
    Use when you need to recall previous decisions, find how a file was modified,
    or look up what happened in earlier sessions.

    Args:
        project: Project slug
        query: Search query (keywords, file names, concepts)
        top_k: Max results to return (default 10)
    """
    from .memory import search
    results = search(project, query, top_k=top_k)
    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# memory_build_context — build the full context block
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_build_context(
    project: str,
    query: str = "",
    max_chars: int = 6000,
) -> str:
    """
    Build and return a rich context block for injection into an agent's system prompt.
    Combines BM25+vector search results with the latest handoff.
    Call this at the start of a session to load relevant project context.

    Args:
        project: Project slug
        query: Optional search query to focus context
        max_chars: Max characters to include (default 6000)
    """
    from .memory import build_context_block
    return build_context_block(project, query or project, max_chars=max_chars)


# ---------------------------------------------------------------------------
# memory_save — explicit long-term memory
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_save(
    project: str,
    content: str,
    confidence: float = 1.0,
) -> str:
    """
    Explicitly save an important insight, decision, or pattern to long-term memory.
    Use for high-value information that should survive consolidation sweeps.
    Different from memory_observe in that it goes directly to the memories table.

    Args:
        project: Project slug
        content: The memory content to save
        confidence: Confidence score 0.0-1.0 (default 1.0)
    """
    from .memory import save
    mem_id = save(project, content, confidence=confidence)
    return json.dumps({"memory_id": mem_id, "status": "saved"})


# ---------------------------------------------------------------------------
# memory_session_start — start a session
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_session_start(
    project: str,
    agent: str,
    feature: str,
) -> str:
    """
    Start a new agent session for a project.
    Call this at the beginning of each coding session.
    Returns a session_id to use in subsequent calls.

    Args:
        project: Project slug
        agent: Agent name (e.g. 'claude-sonnet-4')
        feature: What you're working on (e.g. 'auth-refresh-tokens')
    """
    from .session import start_session
    session_id = start_session(project, agent, feature)
    return json.dumps({"session_id": session_id, "status": "started"})


# ---------------------------------------------------------------------------
# memory_session_close — close a session
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_session_close(
    project: str,
    session_id: int,
    summary: str,
    next_task: str,
    files_modified: str = "",
    open_questions: str = "",
) -> str:
    """
    Close an agent session, generate a handoff for the next agent,
    and run consolidation. Call this when you finish a session.

    Args:
        project: Project slug
        session_id: Session id returned from memory_session_start
        summary: What you accomplished this session
        next_task: What the next agent should do
        files_modified: Comma-separated list of modified files (optional)
        open_questions: Comma-separated list of open questions (optional)
    """
    from .session import close_session
    files = [f.strip() for f in files_modified.split(",") if f.strip()] if files_modified else []
    questions = [q.strip() for q in open_questions.split(",") if q.strip()] if open_questions else []
    close_session(project, session_id, summary, next_task, files, questions)
    return json.dumps({"session_id": session_id, "status": "closed"})


# ---------------------------------------------------------------------------
# memory_sessions — list sessions
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_sessions(project: str, limit: int = 10) -> str:
    """
    List recent sessions for a project with their status and observation counts.
    Use to understand what has been done and who worked on what.

    Args:
        project: Project slug
        limit: Max sessions to return (default 10)
    """
    from .session import list_sessions
    sessions = list_sessions(project, limit=limit)
    return json.dumps(sessions, indent=2)


# ---------------------------------------------------------------------------
# memory_handoff_read — read latest handoff
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_handoff_read(project: str) -> str:
    """
    Read the latest agent handoff for a project.
    Call this at the start of a session to see what the previous agent left for you.

    Args:
        project: Project slug
    """
    from .handoff import format_for_injection, get_latest
    h = get_latest(project)
    if not h:
        return "No handoff found for this project."
    return format_for_injection(project)


# ---------------------------------------------------------------------------
# memory_inject — inject context into agent config files
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_inject(
    project: str,
    adapter: str = "all",
) -> str:
    """
    Inject project memory context into agent configuration files.
    Updates CLAUDE.md, .cursorrules, .github/copilot-instructions.md,
    .gemini/system-prompt.md, and ~/.contextweave/active-context.md.

    Args:
        project: Project slug
        adapter: Which adapter to update: 'claude', 'cursor', 'copilot', 'gemini', 'all' (default 'all')
    """
    from . import inject
    if adapter == "all":
        results = inject.inject_all(project)
    elif adapter == "claude":
        results = [inject.write_claude_md(project)]
    elif adapter == "cursor":
        results = [inject.write_cursorrules(project)]
    elif adapter == "copilot":
        results = [inject.write_copilot(project)]
    elif adapter == "gemini":
        results = [inject.write_gemini(project)]
    else:
        return json.dumps({"error": f"Unknown adapter: {adapter}"})
    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# memory_consolidate — run consolidation sweep
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_consolidate(project: str) -> str:
    """
    Run the memory consolidation sweep: dedup near-duplicate observations,
    apply decay scoring, prune orphan graph nodes, export to vault if configured.
    Run this periodically or after a session to keep the memory store clean.

    Args:
        project: Project slug
    """
    from .consolidate import run_sweep
    stats = run_sweep(project)
    return json.dumps(stats, indent=2)


# ---------------------------------------------------------------------------
# memory_status — project status dashboard
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_status(project: str) -> str:
    """
    Return a status summary for a project: memory counts, last session, health.

    Args:
        project: Project slug
    """
    from .memory import project_stats
    from .session import get_last_session
    from .db import vec_available, DB_PATH
    import os

    stats = project_stats(project)
    last = get_last_session(project)
    db_size = os.path.getsize(str(DB_PATH)) / (1024 * 1024) if DB_PATH.exists() else 0

    return json.dumps({
        "project": project,
        "stats": stats,
        "last_session": last,
        "db_size_mb": round(db_size, 2),
        "vec_available": vec_available(),
    }, indent=2)


# ---------------------------------------------------------------------------
# memory_graph_query — query the knowledge graph
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_graph_query(
    project: str,
    entity: Optional[str] = None,
    depth: int = 2,
) -> str:
    """
    Query the knowledge graph for entities and relationships.
    Returns a subgraph starting from the matching entity.
    Use to understand how concepts, files, and decisions are related.

    Args:
        project: Project slug
        entity: Entity label to start from (e.g. 'src/auth.ts')
        depth: BFS traversal depth (default 2)
    """
    from .graph import build_graph_json, query_entity
    if entity:
        result = query_entity(project, entity, depth=depth)
    else:
        result = build_graph_json(project)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# memory_export — export to Obsidian vault
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_export(project: str) -> str:
    """
    Export all memories for the project to the configured Obsidian vault.
    Creates memory files with YAML frontmatter, PROJECT.md index, and GRAPH.md.

    Args:
        project: Project slug
    """
    from .export import export_to_vault
    count = export_to_vault(project)
    return json.dumps({"files_written": count, "status": "exported"})


# ---------------------------------------------------------------------------
# memory_import_claude — import from Claude Code JSONL transcripts
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_import_claude(project: str) -> str:
    """
    Import observations from Claude Code JSONL transcript files.
    Reads ~/.claude/projects/*/*.jsonl, extracts tool uses and assistant messages,
    and stores them as observations. Use to bootstrap memory from past sessions.

    Args:
        project: Project slug
    """
    from .memory import observe

    claude_projects_dir = Path.home() / ".claude" / "projects"
    if not claude_projects_dir.exists():
        return json.dumps({"imported": 0, "error": "~/.claude/projects/ not found"})

    jsonl_files = list(claude_projects_dir.glob("**/*.jsonl"))
    imported = 0
    errors = 0

    for jsonl_path in jsonl_files:
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type", "")

                    # Extract tool use observations
                    if msg_type == "tool_use":
                        tool_name = msg.get("name", "")
                        tool_input = msg.get("input", {})
                        input_str = json.dumps(tool_input)[:400] if tool_input else ""
                        content = f"Tool used: {tool_name}. Input: {input_str}"
                        observe(project, content, source="import:jsonl:tool_use")
                        imported += 1

                    # Extract tool result observations
                    elif msg_type == "tool_result":
                        content_raw = msg.get("content", "")
                        if isinstance(content_raw, list):
                            # Handle array content blocks
                            texts = [
                                c.get("text", "")[:300]
                                for c in content_raw
                                if isinstance(c, dict) and c.get("type") == "text"
                            ]
                            content_raw = " ".join(texts)
                        if content_raw and str(content_raw).strip():
                            observe(project, str(content_raw)[:500], source="import:jsonl:tool_result")
                            imported += 1

                    # Extract assistant message text
                    elif msg_type == "assistant":
                        msg_content = msg.get("content", [])
                        if isinstance(msg_content, list):
                            for block in msg_content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")[:600]
                                    if text and len(text) > 20:
                                        observe(project, text, source="import:jsonl:assistant")
                                        imported += 1
                        elif isinstance(msg_content, str) and len(msg_content) > 20:
                            observe(project, msg_content[:600], source="import:jsonl:assistant")
                            imported += 1

        except Exception:
            errors += 1

    return json.dumps({
        "imported": imported,
        "files_scanned": len(jsonl_files),
        "errors": errors,
    })


# ---------------------------------------------------------------------------
# memory_brief — generate daily brief
# ---------------------------------------------------------------------------
@mcp.tool()
def memory_brief(project: str) -> str:
    """
    Generate a daily project brief: status, recent activity, open questions,
    top context entities, and the next task. No LLM required.
    Use at the start of a session to quickly understand project state.

    Args:
        project: Project slug
    """
    from .brief import generate_brief
    return generate_brief(project)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run():
    """Start the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    run()
