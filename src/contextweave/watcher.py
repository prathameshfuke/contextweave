import os
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console

from .config import load_config
from .retrieval import Retrieval
from .project import list_projects

console = Console()

class VaultEventHandler(FileSystemEventHandler):
    def __init__(self, retrieval: Retrieval, vault_path: str, target_project: str = None):
        super().__init__()
        self.retrieval = retrieval
        self.vault_path = Path(vault_path)
        self.target_project = target_project

    def _get_project_and_rel_path(self, file_path: str):
        path = Path(file_path)
        try:
            rel_path = path.relative_to(self.vault_path)
            parts = rel_path.parts
            if len(parts) >= 3 and parts[0] == "projects":
                project_slug = parts[1]
                note_rel_path = str(rel_path).replace("\\", "/")
                return project_slug, note_rel_path
        except ValueError:
            pass
        return None, None

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            self._handle_update(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            self._handle_update(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            self._handle_delete(event.src_path)

    def _handle_update(self, src_path: str):
        project_slug, note_rel_path = self._get_project_and_rel_path(src_path)
        if not project_slug:
            return
            
        if self.target_project and project_slug != self.target_project:
            return

        time.sleep(2) # Debounce
        self.retrieval.index_single_note(project_slug, note_rel_path)
        console.print(f"[dim]↻ indexed: {note_rel_path}[/dim]")

    def _handle_delete(self, src_path: str):
        project_slug, note_rel_path = self._get_project_and_rel_path(src_path)
        if not project_slug:
            return
            
        if self.target_project and project_slug != self.target_project:
            return

        self.retrieval.delete_note_from_index(project_slug, note_rel_path)
        console.print(f"[dim]🗑 removed from index: {note_rel_path}[/dim]")

def start_watcher(project_slug: str | None = None):
    config = load_config()
    vault_path = config.get("vault_path")
    if not vault_path or not os.path.exists(vault_path):
        console.print("[red]Vault path not found in config or on disk.[/red]")
        return

    retrieval = Retrieval()
    event_handler = VaultEventHandler(retrieval, vault_path, project_slug)
    observer = Observer()
    
    watch_dir = Path(vault_path) / "projects"
    if project_slug:
        watch_dir = watch_dir / project_slug
    
    if not watch_dir.exists():
        console.print(f"[red]Directory {watch_dir} does not exist.[/red]")
        return

    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()
    
    target_msg = f"'{project_slug}'" if project_slug else "all projects"
    console.print(f"[green]Watching vault ({target_msg}) for changes. Press Ctrl+C to stop.[/green]")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]Watcher stopped.[/yellow]")
    observer.join()
