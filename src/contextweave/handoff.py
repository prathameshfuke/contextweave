from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import frontmatter
from .vault import Vault
from .llm import LLM

class Session:
    def __init__(self, project_slug: str, agent: str, feature: str, file_path: str):
        self.project_slug = project_slug
        self.agent = agent
        self.feature = feature
        self.file_path = file_path

class HandoffManager:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.template_dir = Path(__file__).parent / "templates"
        self.llm = LLM()

    def _load_template(self, name: str) -> str:
        template_path = self.template_dir / f"{name}.md"
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def generate_handoff(self, session: Session, summary: str, next_task: str) -> str:
        # Read session log
        session_content = self.vault.read_note(session.file_path)
        
        # Compress chat (treating the whole file as one turn)
        compressed_content = self.llm.compress_chat([{"role": "assistant", "content": session_content}])
        
        template_content = self._load_template("handoff")
        created = datetime.now().isoformat()
        post = frontmatter.loads(template_content)
        post.metadata.update({
            "from_agent": session.agent,
            "to_agent": "any",
            "project": session.project_slug,
            "feature": session.feature,
            "created": created,
            "next_task": next_task,
        })
        post.content = post.content.replace("{{feature}}", session.feature)
        post.content = post.content.replace("{{summary}}", summary)
        post.content = post.content.replace("{{next_task}}", next_task)
        content = frontmatter.dumps(post)
        content += f"\n\n## LLM Compressed Insights\n{compressed_content}\n"
        
        # Write to handoff-notes.md (append without clobbering prior handoffs)
        handoff_notes_path = Path("projects") / session.project_slug / "agents" / "handoff-notes.md"
        existing_notes = ""
        if self.vault.note_exists(str(handoff_notes_path)):
            existing_notes = self.vault.read_note(str(handoff_notes_path))
        
        if existing_notes.strip():
            new_notes = existing_notes.rstrip() + "\n\n---\n\n" + content
        else:
            new_notes = content
        self.vault.write_note(str(handoff_notes_path), new_notes)
        
        # Write to latest-handoff.md (overwrite)
        latest_handoff_path = Path("projects") / session.project_slug / "agents" / "latest-handoff.md"
        self.vault.write_note(str(latest_handoff_path), content)
        
        return str(latest_handoff_path)

    def get_latest_handoff(self, project_slug: str) -> Optional[Dict[str, Any]]:
        latest_handoff_path = Path("projects") / project_slug / "agents" / "latest-handoff.md"
        if not self.vault.note_exists(str(latest_handoff_path)):
            return None
        
        try:
            content = self.vault.read_note(str(latest_handoff_path))
            post = frontmatter.loads(content)
        except Exception:
            return None
        
        result = dict(post.metadata)
        result["body"] = post.content
        return result

    def format_handoff_for_injection(self, project_slug: str) -> str:
        handoff = self.get_latest_handoff(project_slug)
        if not handoff:
            return ""
        
        return f"""## Previous Agent Handoff
From: {handoff.get('from_agent')}
Feature: {handoff.get('feature')}
Created: {handoff.get('created')}

{handoff.get('body')}
"""
