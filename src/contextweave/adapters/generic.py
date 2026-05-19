from .base import BaseAdapter
from pathlib import Path
from datetime import datetime

class GenericAdapter(BaseAdapter):
    name: str = "generic"

    def inject(self, project_slug: str, context_block: str) -> str:
        config_dir = Path.home() / ".contextweave"
        config_dir.mkdir(parents=True, exist_ok=True)
        active_context = config_dir / "active-context.md"
        
        with open(active_context, "w", encoding="utf-8") as f:
            f.write(context_block)
        
        return str(active_context)

    def read(self, project_slug: str) -> str:
        active_context = Path.home() / ".contextweave" / "active-context.md"
        if not active_context.exists():
            return ""
        with open(active_context, "r", encoding="utf-8") as f:
            return f.read()
