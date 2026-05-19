from abc import ABC, abstractmethod
import os
from pathlib import Path

class BaseAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def inject(self, project_slug: str, context_block: str) -> str:
        """Write context to wherever this agent reads it. Return the path written."""

    @abstractmethod
    def read(self, project_slug: str) -> str:
        """Read whatever context this agent currently has. Return raw string."""

    def get_project_root(self, project_slug: str) -> str:
        """Walk up from cwd to find a folder matching project_slug, else return cwd."""
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if parent.name == project_slug:
                return str(parent)
            # Or if it contains a PROJECT.md (not likely in code root but maybe)
            # Better check for .git or similar to find project root if slug doesn't match folder name
            if (parent / ".git").exists():
                return str(parent)
        return str(cwd)

    def _get_marker_content(self, content: str) -> str:
        start_marker = "<!-- CONTEXTWEAVE START -->"
        end_marker = "<!-- CONTEXTWEAVE END -->"
        if start_marker in content and end_marker in content:
            return content.split(start_marker)[1].split(end_marker)[0].strip()
        return ""

    def _replace_or_append_markers(self, content: str, block: str) -> str:
        start_marker = "<!-- CONTEXTWEAVE START -->"
        end_marker = "<!-- CONTEXTWEAVE END -->"
        new_block = f"{start_marker}\n{block}\n{end_marker}"
        
        if start_marker in content and end_marker in content:
            parts = content.split(start_marker)
            rest = parts[1].split(end_marker)
            return parts[0] + new_block + rest[1]
        else:
            return content + "\n\n" + new_block
