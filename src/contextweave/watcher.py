import os
import time
import threading
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console

from .config import load_config
from .retrieval import Retrieval
from .display import draw_watch_status, create_watch_live

console = Console()

class VaultEventHandler(FileSystemEventHandler):
    def __init__(self, retrieval: Retrieval, vault_path: str, target_project: str = None):
        super().__init__()
        self.retrieval = retrieval
        self.vault_path = Path(vault_path)
        self.target_project = target_project
        self._lock = threading.Lock()
        self._pending_updates = set()
        self._debounce_timer = None
        self._live = None
        self._files_indexed = 0
        self._last_indexed = "never"
        self._last_note = ""

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

        with self._lock:
            self._pending_updates.add((project_slug, note_rel_path))
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(2.0, self._flush_pending_updates)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush_pending_updates(self):
        with self._lock:
            pending = list(self._pending_updates)
            self._pending_updates.clear()
            self._debounce_timer = None

        for project_slug, note_rel_path in sorted(pending):
            self.retrieval.index_single_note(project_slug, note_rel_path)
            self._files_indexed += 1
            self._last_indexed = datetime.now()
            self._last_note = note_rel_path
            if self._live:
                self._live.update(draw_watch_status(self.target_project or "all projects", self._last_indexed, self._files_indexed, self._last_note))

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

    target_msg = project_slug or "all projects"
    initial = draw_watch_status(target_msg, "waiting", 0)
    with create_watch_live(initial, console) as live:
        event_handler._live = live
        live.update(draw_watch_status(target_msg, "waiting", 0))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            console.print("\n[yellow]Watcher stopped.[/yellow]")
    observer.join()
