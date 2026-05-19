from .base import BaseAdapter
from pathlib import Path
from datetime import datetime

class GeminiAdapter(BaseAdapter):
    name: str = "gemini"

    def inject(self, project_slug: str, context_block: str) -> str:
        root = Path(self.get_project_root(project_slug))
        gemini_dir = root / ".gemini"
        gemini_dir.mkdir(exist_ok=True)
        prompt_file = gemini_dir / "system-prompt.md"
        
        content = ""
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()
        
        formatted_block = f"""> **ContextWeave — auto-generated, do not edit this block manually**
> Last updated: {datetime.now().isoformat()}
> Project: {project_slug}

{context_block}"""
        
        new_content = self._replace_or_append_markers(content, formatted_block)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return str(prompt_file)

    def read(self, project_slug: str) -> str:
        root = Path(self.get_project_root(project_slug))
        prompt_file = root / ".gemini" / "system-prompt.md"
        if not prompt_file.exists():
            return ""
        with open(prompt_file, "r", encoding="utf-8") as f:
            return self._get_marker_content(f.read())
