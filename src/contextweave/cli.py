import click
from rich.console import Console
from rich.table import Table
from contextweave.config import load_config, save_config
from contextweave.vault import Vault
from contextweave.project import ProjectManager
from contextweave.session import SessionManager, Session

console = Console()

@click.group()
def main():
    """ContextWeave: Persistent Memory for AI Workflows."""
    pass

@main.command()
@click.argument("slug")
@click.option("--description", default="", help="Project description")
def init(slug, description):
    """Initialize a new project in the vault."""
    config = load_config()
    try:
        vault = Vault(config["vault_path"])
        pm = ProjectManager(vault)
        path = pm.init_project(slug, description)
        console.print(f"[green]Successfully initialized project '{slug}' at {path}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.group()
def session():
    """Manage AI sessions."""
    pass

@session.command(name="start")
@click.argument("project_slug")
@click.option("--agent", required=True, help="Agent name (e.g., claude, gemini)")
@click.option("--feature", required=True, help="Feature being worked on")
def session_start(project_slug, agent, feature):
    """Start a new AI session."""
    config = load_config()
    try:
        vault = Vault(config["vault_path"])
        sm = SessionManager(vault)
        sess = sm.start_session(project_slug, agent, feature)
        console.print(f"[green]Started session for '{project_slug}'. Log created at: {sess.file_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@session.command(name="close")
@click.argument("project_slug")
@click.option("--summary", required=True, help="Summary of work done")
@click.option("--next", "next_task", required=True, help="Next task to perform")
def session_close(project_slug, summary, next_task):
    """Close the last open session for a project."""
    config = load_config()
    try:
        vault = Vault(config["vault_path"])
        sm = SessionManager(vault)
        last_sess_data = sm.get_last_session(project_slug)
        
        if not last_sess_data:
            console.print(f"[yellow]No sessions found for project '{project_slug}'.[/yellow]")
            return

        if last_sess_data.get("status") == "completed":
            console.print(f"[yellow]The last session for '{project_slug}' is already closed.[/yellow]")
            return

        session = Session(
            project_slug=project_slug,
            agent=last_sess_data["agent"],
            feature=last_sess_data["feature"],
            file_path=last_sess_data["file_path"]
        )
        
        sm.close_session(session, summary, next_task)
        console.print(f"[green]Session for '{project_slug}' closed successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.group()
def projects():
    """Project management commands."""
    pass

@projects.command(name="list")
def projects_list():
    """List all projects in the vault."""
    config = load_config()
    try:
        vault = Vault(config["vault_path"])
        pm = ProjectManager(vault)
        projects = pm.list_projects()
        
        if not projects:
            console.print("[yellow]No projects found in the vault.[/yellow]")
            return

        table = Table(title="ContextWeave Projects")
        table.add_column("Slug", style="cyan")
        table.add_column("Description", style="magenta")
        
        for slug in projects:
            try:
                meta = pm.get_project(slug)
                table.add_row(slug, meta.get("description", ""))
            except:
                table.add_row(slug, "[red]Metadata missing[/red]")
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

from .adapters import get_adapter, ADAPTERS
from .handoff import HandoffManager
from .codegraph import CodeGraph
from rich.markdown import Markdown
from .retrieval import Retrieval

@main.command()
@click.argument("project_slug")
def index(project_slug):
    """Index a project's notes for semantic search."""
    try:
        retrieval = Retrieval()
        retrieval.index_vault(project_slug)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
@click.argument("query")
def search(project_slug, query):
    """Search for relevant notes using semantic search."""
    try:
        retrieval = Retrieval()
        result = retrieval.build_context_prompt(project_slug, query)
        console.print(Markdown(result))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.group()
def context():
    """Context management commands."""
    pass

@context.command(name="show")
@click.argument("project_slug")
def context_show(project_slug):
    """Show the context that would be injected for the last session's feature."""
    try:
        config = load_config()
        vault = Vault(config["vault_path"])
        sm = SessionManager(vault)
        last_sess = sm.get_last_session(project_slug)
        
        if not last_sess:
            console.print(f"[yellow]No sessions found for project '{project_slug}'.[/yellow]")
            return

        feature = last_sess.get("feature", "general")
        console.print(f"[blue]Building context for feature: {feature}[/blue]")
        
        retrieval = Retrieval()
        result = retrieval.build_context_prompt(project_slug, feature)
        console.print(Markdown(result))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
@click.option("--adapter", type=click.Choice(list(ADAPTERS.keys())), help="Adapter to use")
@click.option("--all", "all_adapters", is_flag=True, help="Inject into all adapters")
def inject(project_slug, adapter, all_adapters):
    """Inject context into AI agent files."""
    try:
        config = load_config()
        vault = Vault(config["vault_path"])
        sm = SessionManager(vault)
        last_sess = sm.get_last_session(project_slug)
        
        feature = last_sess.get("feature", "general") if last_sess else "general"
        
        retrieval = Retrieval()
        context_block = retrieval.build_context_prompt(project_slug, feature)
        
        # Add handoff to context block
        handoff_mgr = HandoffManager(vault)
        handoff_text = handoff_mgr.format_handoff_for_injection(project_slug)
        if handoff_text:
            context_block = handoff_text + "\n" + context_block

        if all_adapters:
            table = Table(title=f"Context Injection for {project_slug}")
            table.add_column("Adapter", style="cyan")
            table.add_column("File Written", style="magenta")
            table.add_column("Status", style="green")
            
            for name, adap in ADAPTERS.items():
                try:
                    path = adap.inject(project_slug, context_block)
                    table.add_row(name, path, "Success")
                except Exception as e:
                    table.add_row(name, "-", f"[red]Error: {e}[/red]")
            console.print(table)
        elif adapter:
            adap = get_adapter(adapter)
            path = adap.inject(project_slug, context_block)
            console.print(f"[green]Context injected via {adapter} into {path}[/green]")
            console.print("[blue]Preview (first 10 lines):[/blue]")
            console.print("\n".join(context_block.splitlines()[:10]))
        else:
            console.print("[yellow]Please specify --adapter or --all[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.group()
def handoff():
    """Handoff management commands."""
    pass

@handoff.command(name="show")
@click.argument("project_slug")
def handoff_show(project_slug):
    """Show the latest handoff for a project."""
    try:
        config = load_config()
        vault = Vault(config["vault_path"])
        hm = HandoffManager(vault)
        handoff = hm.get_latest_handoff(project_slug)
        
        if not handoff:
            console.print(f"[yellow]No handoff found for '{project_slug}'.[/yellow]")
            return

        console.print(Panel(
            f"[bold cyan]From Agent:[/bold cyan] {handoff.get('from_agent')}\n"
            f"[bold cyan]Feature:[/bold cyan] {handoff.get('feature')}\n"
            f"[bold cyan]Created:[/bold cyan] {handoff.get('created')}\n\n"
            f"{handoff.get('body')}",
            title="Latest Handoff",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
@click.option("--root", default=".", help="Codebase root directory")
def snapshot(project_slug, root):
    """Generate a codebase structure snapshot."""
    try:
        config = load_config()
        vault = Vault(config["vault_path"])
        cg = CodeGraph(vault)
        path = cg.write_snapshot(project_slug, root)
        
        console.print(f"[green]Codebase snapshot generated and written to {path}[/green]")
        console.print("[blue]Preview (first 20 lines):[/blue]")
        content = vault.read_note(path)
        console.print("\n".join(content.splitlines()[:20]))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

from .brief import generate_brief, brief_all_projects
from .watcher import start_watcher
from .diff import latest_diff
from rich.panel import Panel
import requests
import os
from pathlib import Path

@main.command()
@click.argument("project_slug", required=False)
@click.option("--all", "all_projects", is_flag=True, help="Generate brief for all projects")
def brief(project_slug, all_projects):
    """Generate a daily brief for a project."""
    try:
        if all_projects:
            results = brief_all_projects()
            for slug, md in results.items():
                console.print(f"[bold cyan]=== {slug} ===[/bold cyan]")
                console.print(Markdown(md))
                console.print()
        elif project_slug:
            md = generate_brief(project_slug)
            console.print(Markdown(md))
            console.print("[green]✓ Brief saved to vault.[/green]")
        else:
            console.print("[yellow]Provide a project slug or --all.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug", required=False)
def watch(project_slug):
    """Start the file watcher to auto-sync ChromaDB."""
    try:
        start_watcher(project_slug)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
def diff(project_slug):
    """Show the context diff between the last two sessions."""
    try:
        md = latest_diff(project_slug)
        console.print(Markdown(md))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
def status(project_slug):
    """Show the current status of a project."""
    try:
        config = load_config()
        vault = Vault(config["vault_path"])
        sm = SessionManager(vault)
        hm = HandoffManager(vault)
        
        last_sess = sm.get_last_session(project_slug)
        handoff = hm.get_latest_handoff(project_slug)
        
        # Open questions count
        sessions_dir = f"projects/{project_slug}/sessions"
        session_notes = vault.list_notes(sessions_dir)
        open_questions = 0
        for note in session_notes:
            content = vault.read_note(note)
            in_questions = False
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('## Open Questions'):
                    in_questions = True
                elif line.startswith('## '):
                    in_questions = False
                elif in_questions and line.startswith('- ') and not line.startswith('- [x]') and not line.startswith('- [X]'):
                    open_questions += 1

        # Check ChromaDB
        notes_indexed = 0
        try:
            from .retrieval import Retrieval
            client = Retrieval()._get_client()
            col = client.get_collection(name=project_slug)
            notes_indexed = col.count()
        except:
            pass

        # Check Obsidian API
        obsidian_reachable = False
        try:
            res = requests.get("http://127.0.0.1:27123/", timeout=1)
            if res.status_code in [200, 401, 403, 404]: # 401/403 means it's running but needs auth
                obsidian_reachable = True
        except:
            pass

        # Check Ollama
        ollama_running = False
        try:
            res = requests.get("http://127.0.0.1:11434/", timeout=1)
            if res.status_code == 200:
                ollama_running = True
        except:
            pass

        # Display
        console.print(f"[bold cyan]Status: {project_slug}[/bold cyan]")
        
        t = Table(show_header=False, box=None)
        if last_sess:
            t.add_row("Last Session:", f"{last_sess.get('agent', '?')} working on [green]{last_sess.get('feature', '?')}[/green]")
            t.add_row("Status:", last_sess.get('status', '?'))
            t.add_row("Started:", last_sess.get('started', '?'))
        else:
            t.add_row("Last Session:", "None")

        next_step = handoff.get("next_step", "None") if handoff else "None"
        t.add_row("Next Step:", f"[bold magenta]{next_step}[/bold magenta]")
        t.add_row("Open Questions:", str(open_questions))
        t.add_row("Notes Indexed:", str(notes_indexed))
        t.add_row("Obsidian API:", "[green]✓[/green]" if obsidian_reachable else "[red]✗[/red]")
        t.add_row("Ollama:", "[green]✓[/green]" if ollama_running else "[red]✗[/red]")
        
        console.print(Panel(t, border_style="blue"))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
def doctor():
    """Diagnoses the full setup."""
    console.print("[bold cyan]ContextWeave Doctor[/bold cyan]\n")
    config = load_config()
    
    issues = []
    
    # Vault Path
    vault_path = config.get("vault_path")
    if vault_path and os.path.exists(vault_path):
        console.print("[green]✓[/green] Vault path exists on disk")
    else:
        console.print("[red]✗[/red] Vault path does not exist")
        issues.append("Vault path not found. Run: [cyan]contextweave init[/cyan] or edit ~/.contextweave/config.toml")
        
    # Obsidian API
    obsidian_reachable = False
    try:
        res = requests.get("http://127.0.0.1:27123/", timeout=2)
        if res.status_code in [200, 401, 403, 404]: 
            obsidian_reachable = True
    except:
        pass
    
    if obsidian_reachable:
        console.print("[green]✓[/green] Obsidian Local REST API reachable")
    else:
        console.print("[red]✗[/red] Obsidian Local REST API not reachable")
        issues.append("Obsidian API not found. Install 'Local REST API' plugin in Obsidian and set port to 27123.")
        
    # Ollama
    ollama_running = False
    model_pulled = False
    try:
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if res.status_code == 200:
            ollama_running = True
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            if "mistral:latest" in models or "mistral" in models:
                model_pulled = True
    except:
        pass
        
    if ollama_running:
        console.print("[green]✓[/green] Ollama running")
        if model_pulled:
            console.print("[green]✓[/green] Ollama mistral model pulled")
        else:
            console.print("[red]✗[/red] Ollama mistral model not pulled")
            issues.append("Ollama mistral model not found. Run: [cyan]ollama pull mistral[/cyan]")
    else:
        console.print("[red]✗[/red] Ollama running")
        issues.append("Ollama not running. Install from ollama.com and run: [cyan]OLLAMA_ORIGINS=* ollama serve[/cyan]")
        
    # ChromaDB
    chroma_path = Path.home() / ".contextweave" / "chroma"
    if chroma_path.exists():
        console.print("[green]✓[/green] ChromaDB folder exists")
    else:
        console.print("[red]✗[/red] ChromaDB folder does not exist")
        issues.append("ChromaDB not initialized. Start a session or run index.")
        
    # Projects
    pm = ProjectManager(Vault(vault_path)) if vault_path else None
    if pm and pm.list_projects():
        console.print("[green]✓[/green] At least one project exists")
    else:
        console.print("[red]✗[/red] At least one project exists")
        issues.append("No projects found. Run: [cyan]contextweave init <project-slug>[/cyan]")
        
    if issues:
        console.print("\n[bold yellow]Fix the following issues:[/bold yellow]")
        for i, issue in enumerate(issues, 1):
            console.print(f"{i}. {issue}")
    else:
        console.print("\n[bold green]All systems go! Ready to weave context.[/bold green]")

if __name__ == "__main__":
    main()
