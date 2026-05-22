"""
_cli_entry.py — Full CLI entry point for the contextweave console script.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Windows UTF-8 fix ────────────────────────────────────────────────────────
# Rich uses Unicode symbols (✓, ●, 🧠) that Windows cp1252 cannot encode.
# Force stdout/stderr to UTF-8 on Windows before rich initialises.
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

console = Console(highlight=False)


def _time_ago(iso_str: str) -> str:
    if not iso_str:
        return "?"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str)
        diff = datetime.utcnow() - dt
        s = int(diff.total_seconds())
        if s < 60: return f"{s}s"
        if s < 3600: return f"{s // 60}m"
        if s < 86400: return f"{s // 3600}h"
        return f"{s // 86400}d"
    except Exception:
        return "?"


@click.group()
def main():
    """🧠 ContextWeave — persistent memory layer for AI coding agents."""
    try:
        from contextweave.db import init_db
        init_db()
    except Exception:
        pass


@main.command()
@click.argument("project")
@click.option("--description", "-d", default="", help="Project description")
@click.option("--vault", "-v", default="", help="Obsidian vault path (optional)")
def init(project: str, description: str, vault: str):
    """Initialize a new project."""
    from contextweave.db import ensure_project, init_db
    init_db()
    pid = ensure_project(project, description=description, vault_path=vault)
    console.print(Panel(
        f"[green]✓[/green] Project [bold cyan]{project}[/bold cyan] initialized (id={pid})\n\n"
        f"Next steps:\n"
        f"  [dim]contextweave hooks install {project}[/dim]\n"
        f"  [dim]contextweave observe {project} \"first observation\"[/dim]\n"
        f"  [dim]contextweave serve[/dim]",
        title="[bold]Project Created[/bold]",
        border_style="purple",
    ))


@main.command()
@click.argument("project")
@click.argument("content")
@click.option("--source", "-s", default="cli", help="Source identifier")
@click.option("--agent", "-a", default=None, help="Agent name")
@click.option("--tags", "-t", default="", help="Comma-separated tags")
def observe(project: str, content: str, source: str, agent, tags: str):
    """Capture an observation/memory for a project."""
    from contextweave.memory import observe as _observe
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    obs_id = _observe(project, content, source=source, agent=agent, tags=tag_list)
    console.print(f"[green]✓[/green] Observation [bold]#{obs_id}[/bold] captured → [cyan]{project}[/cyan]")


@main.command()
@click.argument("project")
@click.argument("query")
@click.option("--top-k", "-k", default=10, help="Max results")
def search(project: str, query: str, top_k: int):
    """Search observations using BM25 + vector hybrid search."""
    from contextweave.memory import search as _search

    with Progress(SpinnerColumn(), TextColumn("[dim]Searching..."), transient=True) as p:
        p.add_task("", total=None)
        results = _search(project, query, top_k=top_k)

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    table = Table(title=f"Search: '{query}' in {project}", border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("Content", min_width=40)
    table.add_column("Source", style="cyan", width=22)
    table.add_column("Agent", style="magenta", width=12)
    table.add_column("Score", style="yellow", width=7)
    table.add_column("Time", style="dim", width=12)

    for i, r in enumerate(results, 1):
        content_preview = (r["content"] or "")[:80] + ("…" if len(r["content"] or "") > 80 else "")
        table.add_row(
            str(i),
            content_preview,
            (r.get("source") or "")[:22],
            (r.get("agent") or "—")[:12],
            f"{r.get('score', 0):.3f}",
            _time_ago(r.get("created_at", "")),
        )
    console.print(table)


@main.group()
def session():
    """Session lifecycle commands."""
    pass


@session.command("start")
@click.argument("project")
@click.option("--agent", "-a", required=True, help="Agent name")
@click.option("--feature", "-f", required=True, help="Feature being worked on")
def session_start(project: str, agent: str, feature: str):
    """Start a new session."""
    from contextweave.session import start_session
    session_id = start_session(project, agent, feature)
    console.print(Panel(
        f"Session [bold]#{session_id}[/bold] started\n"
        f"[dim]Project:[/dim] {project}\n"
        f"[dim]Agent:[/dim]   {agent}\n"
        f"[dim]Feature:[/dim] {feature}",
        title="[bold green]Session Started[/bold green]",
        border_style="green",
    ))


@session.command("close")
@click.argument("project")
@click.option("--summary", "-s", required=True, help="What was accomplished")
@click.option("--next", "next_task", "-n", required=True, help="Next task")
@click.option("--session-id", default=None, type=int)
@click.option("--files", "-f", default="")
@click.option("--questions", "-q", default="")
def session_close(project: str, summary: str, next_task: str, session_id, files: str, questions: str):
    """Close a session and generate a handoff."""
    from contextweave.session import get_last_session, close_session
    if session_id is None:
        last = get_last_session(project)
        if last is None:
            console.print("[red]No active session found.[/red]")
            return
        session_id = last["id"]
    file_list = [f.strip() for f in files.split(",") if f.strip()]
    q_list = [q.strip() for q in questions.split(",") if q.strip()]
    close_session(project, session_id, summary, next_task, file_list, q_list)
    console.print(Panel(
        f"Session [bold]#{session_id}[/bold] closed.\n"
        f"Next task: [bold cyan]{next_task}[/bold cyan]",
        title="[bold green]Session Closed[/bold green]",
        border_style="green",
    ))


@main.group()
def handoff():
    """Handoff commands."""
    pass


@handoff.command("show")
@click.argument("project")
def handoff_show(project: str):
    """Show the latest handoff for a project."""
    from contextweave.handoff import format_for_injection, get_latest
    h = get_latest(project)
    if not h:
        console.print("[dim]No handoff found.[/dim]")
        return
    content = format_for_injection(project)
    console.print(Panel(content, title="[bold purple]Latest Handoff[/bold purple]", border_style="purple"))


@main.command()
@click.argument("project")
@click.option("--adapter", "-a", default="all",
              type=click.Choice(["claude", "cursor", "copilot", "gemini", "all"]))
def inject(project: str, adapter: str):
    """Inject context into agent config files."""
    from contextweave import inject as _inj
    table = Table(title="Context Injection Results", border_style="dim")
    table.add_column("Adapter", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Status")
    if adapter == "all":
        results = _inj.inject_all(project)
    elif adapter == "claude":
        results = [_inj.write_claude_md(project)]
    elif adapter == "cursor":
        results = [_inj.write_cursorrules(project)]
    elif adapter == "copilot":
        results = [_inj.write_copilot(project)]
    else:
        results = [_inj.write_gemini(project)]
    for r in results:
        c = "green" if "error" not in r["status"] else "red"
        table.add_row(r["adapter"], r["path"], f"[{c}]{r['status']}[/{c}]")
    console.print(table)


@main.group()
def hooks():
    """Hook management commands."""
    pass


@hooks.command("install")
@click.argument("project")
@click.option("--all-agents", is_flag=True, default=False)
def hooks_install(project: str, all_agents: bool):
    """Install Claude Code hooks into .claude/hooks/."""
    from contextweave.hooks import generate_hooks, generate_all_hooks
    fn = generate_all_hooks if all_agents else generate_hooks
    results = fn(project)
    table = Table(title="Hooks Installed", border_style="dim")
    table.add_column("Hook Event", style="cyan")
    table.add_column("File", style="dim")
    table.add_column("Status")
    for r in results:
        table.add_row(r["hook_event"], Path(r["file"]).name, f"[green]{r['status']}[/green]")
    console.print(table)
    console.print(f"\n[dim]Set:[/dim] [bold]CONTEXTWEAVE_PROJECT={project}[/bold]")


@main.command()
@click.argument("project")
def consolidate(project: str):
    """Run consolidation sweep: dedup, decay, prune, export."""
    from contextweave.consolidate import run_sweep
    with Progress(SpinnerColumn(), TextColumn("[dim]Running sweep..."), transient=True) as p:
        p.add_task("", total=None)
        stats = run_sweep(project)
    console.print(Panel(
        f"[green]✓[/green] Consolidation complete\n\n"
        f"  Merged: [bold]{stats.get('merged', 0)}[/bold]  "
        f"Deleted: [bold]{stats.get('deleted', 0)}[/bold]  "
        f"Decayed: [bold]{stats.get('decayed', 0)}[/bold]  "
        f"Orphans: [bold]{stats.get('orphans_pruned', 0)}[/bold]",
        title="[bold]Consolidation Results[/bold]",
        border_style="purple",
    ))


@main.command()
@click.argument("project")
def export(project: str):
    """Export memories to Obsidian vault."""
    from contextweave.export import export_to_vault
    count = export_to_vault(project)
    if count == 0:
        console.print("[yellow]No vault configured. Use --vault on contextweave init.[/yellow]")
    else:
        console.print(f"[green]✓[/green] Exported [bold]{count}[/bold] files.")


@main.command()
@click.argument("project")
def watch(project: str):
    """Watch DB for changes and auto-export."""
    from contextweave.export import watch_and_export
    watch_and_export(project)


@main.command()
@click.argument("project")
@click.option("--entity", "-e", default=None)
def graph(project: str, entity):
    """Display the knowledge graph."""
    from contextweave.graph import top_nodes, query_entity
    nodes = top_nodes(project, limit=30)
    if not nodes:
        console.print("[dim]No graph data yet.[/dim]")
        return
    table = Table(title=f"Knowledge Graph — {project}", border_style="dim")
    table.add_column("Label", min_width=30)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Mentions", style="yellow", width=10, justify="right")
    for n in nodes:
        table.add_row(n["label"], n.get("type") or "entity", str(n["observation_count"]))
    console.print(table)
    if entity:
        data = query_entity(project, entity, depth=2)
        console.print(f"\n[dim]Subgraph '{entity}': {len(data['nodes'])} nodes, {len(data['links'])} edges[/dim]")


@main.command()
@click.argument("project")
def brief(project: str):
    """Generate and display the daily project brief."""
    from contextweave.brief import generate_brief
    with Progress(SpinnerColumn(), TextColumn("[dim]Generating..."), transient=True) as p:
        p.add_task("", total=None)
        text = generate_brief(project)
    console.print(Syntax(text, "markdown", theme="monokai", word_wrap=True))


@main.command("import-claude")
@click.argument("project")
def import_claude(project: str):
    """Import from Claude Code JSONL transcripts."""
    from contextweave.memory import observe
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        console.print("[red]~/.claude/projects/ not found[/red]")
        return
    jsonl_files = list(claude_dir.glob("**/*.jsonl"))
    console.print(f"[dim]Found {len(jsonl_files)} JSONL files...[/dim]")
    imported = 0
    with Progress(SpinnerColumn(), TextColumn("[dim]Importing..."), transient=True) as p:
        task = p.add_task("", total=len(jsonl_files))
        for jf in jsonl_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            msg = json.loads(line)
                        except Exception:
                            continue
                        mt = msg.get("type", "")
                        if mt == "tool_use":
                            tool = msg.get("name", "")
                            inp = json.dumps(msg.get("input", {}))[:300]
                            observe(project, f"Tool: {tool}. {inp}", source="import:jsonl")
                            imported += 1
                        elif mt == "assistant":
                            mc = msg.get("content", [])
                            if isinstance(mc, list):
                                for blk in mc:
                                    if isinstance(blk, dict) and blk.get("type") == "text":
                                        text = blk.get("text", "")[:500]
                                        if len(text) > 20:
                                            observe(project, text, source="import:jsonl:assistant")
                                            imported += 1
            except Exception:
                pass
            p.advance(task)
    console.print(f"[green]✓[/green] Imported [bold]{imported}[/bold] observations.")


@main.command()
@click.option("--port", "-p", default=4222)
def serve(port: int):
    """Start the web viewer on localhost:<port>."""
    import threading, webbrowser, time, urllib.request
    url = f"http://localhost:{port}"
    console.print(Panel(
        f"[bold]ContextWeave Viewer[/bold]\n\n"
        f"  [dim]URL:[/dim] [link={url}]{url}[/link]\n"
        f"  [dim]Press Ctrl+C to stop[/dim]",
        title="🌐 Web Viewer", border_style="purple",
    ))
    def open_browser():
        start_time = time.time()
        while time.time() - start_time < 5:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.2)
        webbrowser.open(url)
    threading.Thread(target=open_browser, daemon=True).start()
    from contextweave.viewer.app import run
    run(port=port)


@main.command()
def mcp():
    """Start the MCP server (stdio transport)."""
    console.print("[dim]Starting ContextWeave MCP server (stdio)...[/dim]", file=sys.stderr)
    from contextweave.mcp_server import run
    run()


@main.command()
def doctor():
    """Run health checks."""
    checks = []
    from contextweave.db import DB_PATH, init_db
    try:
        init_db()
        checks.append(("Database", "~/.contextweave/cw.db", True, str(DB_PATH)))
    except Exception as e:
        checks.append(("Database", str(e), False, ""))

    try:
        from contextweave.db import vec_available
        avail = vec_available()
        checks.append(("sqlite-vec", "vector search", avail, "BM25-only mode" if not avail else "384-dim embeddings"))
    except Exception as e:
        checks.append(("sqlite-vec", str(e), False, ""))

    try:
        from sentence_transformers import SentenceTransformer
        checks.append(("sentence-transformers", "all-MiniLM-L6-v2", True, "ready"))
    except ImportError:
        checks.append(("sentence-transformers", "not installed", False, "pip install sentence-transformers"))

    try:
        from mcp.server.fastmcp import FastMCP
        checks.append(("MCP", "fastmcp", True, "15 tools"))
    except ImportError:
        checks.append(("MCP", "not installed", False, "pip install mcp[cli]"))

    try:
        import fastapi
        checks.append(("FastAPI", f"v{fastapi.__version__}", True, "viewer on :4222"))
    except ImportError:
        checks.append(("FastAPI", "not installed", False, "pip install fastapi uvicorn"))

    table = Table(title="ContextWeave Doctor", border_style="dim")
    table.add_column("Check", style="bold", width=22)
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    all_ok = True
    for name, status, ok, detail in checks:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        status_str = f"[green]{status}[/green]" if ok else f"[red]{status}[/red]"
        table.add_row(name, f"{icon} {status_str}", detail)
        if not ok: all_ok = False

    console.print(table)
    if all_ok:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print("\n[yellow]Some checks failed.[/yellow]")
        sys.exit(1)


@main.command()
@click.argument("project")
def status(project: str):
    """Show project status dashboard."""
    from contextweave.memory import project_stats
    from contextweave.session import get_last_session
    from contextweave.handoff import get_latest
    from contextweave.db import DB_PATH, vec_available

    stats = project_stats(project)
    last = get_last_session(project)
    handoff = get_latest(project)
    db_size = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0

    db_dot = "[green]●[/green]" if DB_PATH.exists() else "[red]●[/red]"
    vec_dot = "[green]●[/green]" if vec_available() else "[yellow]●[/yellow]"

    lines = [
        f"[bold]Project:[/bold] [cyan]{project}[/cyan]   {db_dot} DB  {vec_dot} Vec",
        "",
        f"  [dim]Observations:[/dim]  [bold]{stats['observations']}[/bold]",
        f"  [dim]Memories:[/dim]      [bold]{stats['memories']}[/bold]",
        f"  [dim]Sessions:[/dim]      [bold]{stats['sessions']}[/bold]",
        f"  [dim]Graph nodes:[/dim]   [bold]{stats['graph_nodes']}[/bold]",
        f"  [dim]DB size:[/dim]       [bold]{db_size:.2f} MB[/bold]",
    ]
    if last:
        lines += [
            "", f"  [dim]Last agent:[/dim]    [bold]{last.get('agent', '—')}[/bold]",
            f"  [dim]Feature:[/dim]       {last.get('feature', '—')}",
            f"  [dim]Status:[/dim]        {last.get('status', '—')}",
        ]
        if last.get("summary"):
            lines.append(f"  [dim]Summary:[/dim]       {last['summary'][:60]}…")
    if handoff:
        lines += ["", f"  [dim]Next task:[/dim]     [bold yellow]{handoff.get('next_task', '—')}[/bold yellow]"]

    console.print(Panel("\n".join(lines), title="[bold]Project Status[/bold]", border_style="purple"))
