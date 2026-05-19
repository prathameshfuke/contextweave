from .base import BaseAdapter
from pathlib import Path
from datetime import datetime

class CopilotAdapter(BaseAdapter):
    name: str = "copilot"

    def inject(self, project_slug: str, context_block: str) -> str:
        root = Path(self.get_project_root(project_slug))
        github_dir = root / ".github"
        github_dir.mkdir(exist_ok=True)
        instruction_file = github_dir / "copilot-instructions.md"
        
        content = ""
        if instruction_file.exists():
            with open(instruction_file, "r", encoding="utf-8") as f:
                content = f.read()
        
        formatted_block = f"""> **ContextWeave — auto-generated, do not edit this block manually**
> Last updated: {datetime.now().isoformat()}
> Project: {project_slug}

{context_block}"""
        
        new_content = self._replace_or_append_markers(content, formatted_block)
        with open(instruction_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return str(instruction_file)

    def read(self, project_slug: str) -> str:
        root = Path(self.get_project_root(project_slug))
        instruction_file = root / ".github" / "copilot-instructions.md"
        if not instruction_file.exists():
            return ""
        with open(instruction_file, "r", encoding="utf-8") as f:
            return self._get_marker_content(f.read())
