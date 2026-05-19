from .base import BaseAdapter
from pathlib import Path
from datetime import datetime

class ClaudeCodeAdapter(BaseAdapter):
    name: str = "claude"

    def inject(self, project_slug: str, context_block: str) -> str:
        root = Path(self.get_project_root(project_slug))
        claude_md = root / "CLAUDE.md"
        
        content = ""
        if claude_md.exists():
            with open(claude_md, "r", encoding="utf-8") as f:
                content = f.read()
        
        formatted_block = f"""> **ContextWeave — auto-generated, do not edit this block manually**
> Last updated: {datetime.now().isoformat()}
> Project: {project_slug}

{context_block}"""
        
        new_content = self._replace_or_append_markers(content, formatted_block)
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return str(claude_md)

    def read(self, project_slug: str) -> str:
        root = Path(self.get_project_root(project_slug))
        claude_md = root / "CLAUDE.md"
        if not claude_md.exists():
            return ""
        with open(claude_md, "r", encoding="utf-8") as f:
            return self._get_marker_content(f.read())
