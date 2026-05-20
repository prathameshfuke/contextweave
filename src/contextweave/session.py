from datetime import datetime
from typing import Dict, Any, Optional
import frontmatter
from pathlib import Path
from .vault import Vault
from .handoff import HandoffManager, Session
from rich.console import Console
from .display import draw_handoff_panel

console = Console()

def _metadata_timestamp(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

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
            console.print(draw_handoff_panel(latest_handoff))

        started = datetime.now()
        date_str = started.strftime("%Y-%m-%d")
        session_filename = f"{date_str}-{agent}-{feature}.md"
        relative_path = Path("projects") / project_slug / "sessions" / session_filename
        
        template_content = self._load_template("session-log")
        post = frontmatter.loads(template_content)
        post.metadata.update({
            "project": project_slug,
            "agent": agent,
            "feature": feature,
            "status": "in-progress",
            "started": started.isoformat(),
            "ended": "",
            "tags": [],
        })
        post.content = post.content.replace("{{feature}}", feature)
        content = frontmatter.dumps(post)
        
        self.vault.write_note(str(relative_path), content)
        return Session(project_slug, agent, feature, str(relative_path))

    def close_session(self, session: Session, summary: str, next_task: str) -> None:
        content = self.vault.read_note(session.file_path)
        post = frontmatter.loads(content)
        
        post.metadata["status"] = "completed"
        post.metadata["ended"] = datetime.now().isoformat()
        post.metadata["started"] = _metadata_timestamp(post.metadata.get("started"))
        post.metadata["ended"] = _metadata_timestamp(post.metadata.get("ended"))
        
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
        
        parsed_sessions = []
        for note_path in session_notes:
            try:
                content = self.vault.read_note(note_path)
                post = frontmatter.loads(content)
                started = post.get("started")
                if started:
                    started_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                    if started_dt.tzinfo:
                        started_dt = started_dt.replace(tzinfo=None)
                    parsed_sessions.append((started_dt, note_path, post))
            except Exception:
                continue

        if not parsed_sessions:
            return None

        parsed_sessions.sort(key=lambda item: item[0], reverse=True)
        _, last_session_path, post = parsed_sessions[0]
        
        result = dict(post.metadata)
        result["content"] = post.content
        result["file_path"] = last_session_path
        return result
