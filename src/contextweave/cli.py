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

if __name__ == "__main__":
    main()
