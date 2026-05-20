import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import frontmatter
from .vault import Vault
from .llm import LLM

class CodeGraph:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.llm = LLM()

    def scan_project(self, root_dir: str, project_slug: str) -> Dict[str, Any]:
        root = Path(root_dir).resolve()
        skip_dirs = {"node_modules", ".git", "__pycache__", "dist", ".next", "venv", ".venv"}
        
        scanned_files = []
        by_extension = {}
        top_level_folders = set()

        for current_root, dirs, files in os.walk(root, followlinks=False):
            # Prune dirs
            dirs[:] = [
                d for d in dirs
                if d not in skip_dirs and not (Path(current_root) / d).is_symlink()
            ]
            
            rel_root = Path(current_root).relative_to(root)
            if rel_root.parts:
                top_level_folders.add(rel_root.parts[0])
            
            for file in files:
                file_path = Path(current_root) / file
                try:
                    if file_path.is_symlink():
                        continue
                    stats = file_path.stat()
                    if stats.st_size > 500 * 1024:
                        continue
                        
                    ext = file_path.suffix
                    rel_path = str(file_path.relative_to(root))
                    
                    file_info = {
                        "path": rel_path,
                        "extension": ext,
                        "size": stats.st_size,
                        "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
                    }
                    
                    scanned_files.append(file_info)
                    if ext not in by_extension:
                        by_extension[ext] = []
                    by_extension[ext].append(rel_path)
                    
                except Exception:
                    continue

        return {
            "scanned_at": datetime.now().isoformat(),
            "root": str(root),
            "total_files": len(scanned_files),
            "by_extension": by_extension,
            "top_level_folders": list(top_level_folders)
        }

    def write_snapshot(self, project_slug: str, root_dir: str):
        graph = self.scan_project(root_dir, project_slug)
        
        # Build a raw file tree for the LLM
        file_tree = ""
        for ext, files in graph["by_extension"].items():
            file_tree += f"\n### {ext} files\n"
            for f in files[:20]: # Limit to 20 files per extension for summary
                file_tree += f"- {f}\n"
            if len(files) > 20:
                file_tree += f"- ... and {len(files) - 20} more\n"

        summary_instruction = f"Summarise this codebase structure. It has {graph['total_files']} files across these folders: {', '.join(graph['top_level_folders'])}."
        summary = self.llm.summarise(file_tree, summary_instruction)
        
        snapshot_md_path = Path("projects") / project_slug / "context" / "codebase-snapshot.md"
        metadata = {
            "scanned_at": graph["scanned_at"],
            "root": graph["root"],
            "total_files": graph["total_files"]
        }
        
        content = f"# Codebase Snapshot: {project_slug}\n\n## AI Summary\n{summary}\n\n## File Tree\n{file_tree}"
        
        post = frontmatter.Post(content, **metadata)
        self.vault.write_note(str(snapshot_md_path), frontmatter.dumps(post))
        
        return str(snapshot_md_path)
