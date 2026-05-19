with open("src/contextweave/cli.py", "a", encoding="utf-8") as f:
    f.write("""
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
    \"\"\"Generate a daily brief for a project.\"\"\"
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
    \"\"\"Start the file watcher to auto-sync ChromaDB.\"\"\"
    try:
        start_watcher(project_slug)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
def diff(project_slug):
    \"\"\"Show the context diff between the last two sessions.\"\"\"
    try:
        md = latest_diff(project_slug)
        console.print(Markdown(md))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@main.command()
@click.argument("project_slug")
def status(project_slug):
    \"\"\"Show the current status of a project.\"\"\"
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
            for line in content.split('\\n'):
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
    \"\"\"Diagnoses the full setup.\"\"\"
    console.print("[bold cyan]ContextWeave Doctor[/bold cyan]\\n")
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
        console.print("\\n[bold yellow]Fix the following issues:[/bold yellow]")
        for i, issue in enumerate(issues, 1):
            console.print(f"{i}. {issue}")
    else:
        console.print("\\n[bold green]All systems go! Ready to weave context.[/bold green]")

""")
