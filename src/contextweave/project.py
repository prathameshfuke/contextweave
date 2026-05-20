from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import frontmatter
from .vault import Vault
from .config import load_config

class ProjectManager:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.projects_base = Path("projects")

    def init_project(self, slug: str, description: str = "") -> str:
        project_path = self.projects_base / slug
        
        # Create directories
        directories = [
            project_path / "context",
            project_path / "sessions",
            project_path / "web-captures",
            project_path / "agents"
        ]
        
        for doc_dir in directories:
            (self.vault.vault_path / doc_dir).mkdir(parents=True, exist_ok=True)

        # Initialize PROJECT.md
        project_md_path = project_path / "PROJECT.md"
        metadata = {
            "slug": slug,
            "created": datetime.now().isoformat(),
            "description": description
        }
        content = f"# Project: {slug}\n\n{description}"
        
        post = frontmatter.Post(content, **metadata)
        self.vault.write_note(str(project_md_path), frontmatter.dumps(post))

        # Create core context files if they don't exist
        context_files = ["architecture.md", "decisions.md", "in-progress.md"]
        for cf in context_files:
            cf_path = project_path / "context" / cf
            if not self.vault.note_exists(str(cf_path)):
                self.vault.write_note(str(cf_path), f"# {cf.replace('.md', '').title()}\n")

        # Create agent files
        agent_files = ["handoff-notes.md", "open-loops.md"]
        for af in agent_files:
            af_path = project_path / "agents" / af
            if not self.vault.note_exists(str(af_path)):
                self.vault.write_note(str(af_path), f"# {af.replace('.md', '').replace('-', ' ').title()}\n")

        return str(self.vault.vault_path / project_path)

    def get_project(self, slug: str) -> Dict[str, Any]:
        project_md_path = self.projects_base / slug / "PROJECT.md"
        if not self.vault.note_exists(str(project_md_path)):
            raise ValueError(f"Project '{slug}' not found.")
        
        content = self.vault.read_note(str(project_md_path))
        post = frontmatter.loads(content)
        return dict(post.metadata)

    def list_projects(self) -> List[str]:
        projects_dir = self.vault.vault_path / self.projects_base
        if not projects_dir.exists():
            return []
        return [d.name for d in projects_dir.iterdir() if d.is_dir()]

def list_projects() -> List[str]:
    config = load_config()
    vault = Vault(config["vault_path"])
    return ProjectManager(vault).list_projects()
