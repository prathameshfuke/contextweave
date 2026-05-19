from datetime import datetime
from typing import Dict, Any, Optional
import frontmatter
from pathlib import Path
from .vault import Vault
from .handoff import HandoffManager, Session
from rich.console import Console
from rich.panel import Panel

console = Console()

class SessionManager:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.template_dir = Path(__file__).parent / "templates"
        self.handoff_mgr = HandoffManager(vault)

    def _load_template(self, name: str) -> str:
        template_path = self.template_dir / f"{name}.md"
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def start_session(self, project_slug: str, agent: str, feature: str) -> Session:
        # Check for latest handoff
        latest_handoff = self.handoff_mgr.get_latest_handoff(project_slug)
        if latest_handoff:
            console.print(Panel(
                f"[bold cyan]Previous Agent:[/bold cyan] {latest_handoff.get('from_agent')}\n"
                f"[bold cyan]Feature:[/bold cyan] {latest_handoff.get('feature')}\n"
                f"[bold yellow]Exact Next Step:[/bold yellow] {latest_handoff.get('next_task', 'Check latest-handoff.md')}",
                title="Context Transfer Waiting",
                border_style="yellow"
            ))
        else:
            console.print("[blue]No previous handoff found for this project.[/blue]")

        date_str = datetime.now().strftime("%Y-%m-%d")
        session_filename = f"{date_str}-{agent}-{feature}.md"
        relative_path = Path("projects") / project_slug / "sessions" / session_filename
        
        template_content = self._load_template("session-log")
        
        # Simple template replacement
        content = template_content.replace("{{project}}", project_slug)
        content = content.replace("{{agent}}", agent)
        content = content.replace("{{feature}}", feature)
        content = content.replace("{{started}}", datetime.now().isoformat())
        
        self.vault.write_note(str(relative_path), content)
        return Session(project_slug, agent, feature, str(relative_path))

    def close_session(self, session: Session, summary: str, next_task: str) -> None:
        content = self.vault.read_note(session.file_path)
        post = frontmatter.loads(content)
        
        post.metadata["status"] = "completed"
        post.metadata["ended"] = datetime.now().isoformat()
        
        # Append summary and next task to the end of the markdown
        new_content = post.content
        new_content += f"\n\n## Session Summary\n{summary}\n"
        new_content += f"\n## Next Task\n{next_task}\n"
        
        post.content = new_content
        self.vault.write_note(session.file_path, frontmatter.dumps(post))

        # Generate Handoff
        handoff_path = self.handoff_mgr.generate_handoff(session, summary, next_task)
        console.print(f"[green]Handoff protocol executed. Latest handoff: {handoff_path}[/green]")

    def get_last_session(self, project_slug: str) -> Optional[Dict[str, Any]]:
        sessions_dir = Path("projects") / project_slug / "sessions"
        session_notes = self.vault.list_notes(str(sessions_dir))
        
        if not session_notes:
            return None
        
        # Sort by filename (which starts with date)
        session_notes.sort(reverse=True)
        last_session_path = session_notes[0]
        
        content = self.vault.read_note(last_session_path)
        post = frontmatter.loads(content)
        
        result = dict(post.metadata)
        result["content"] = post.content
        result["file_path"] = last_session_path
        return result
