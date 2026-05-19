from pathlib import Path
from typing import List, Optional
import os
from .vault_api import VaultAPI
from .config import load_config

class Vault:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path).expanduser().resolve()
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {self.vault_path}")
        
        config = load_config()
        self.api = VaultAPI(config.get("obsidian_api_key", ""), config.get("obsidian_port", 27123))

    def _get_full_path(self, relative_path: str) -> Path:
        return (self.vault_path / relative_path).resolve()

    def read_note(self, path: str) -> str:
        if self.api.is_available():
            try:
                return self.api.read_note(path)
            except:
                pass # Fallback to filesystem
        
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"Note not found: {full_path}")
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def write_note(self, path: str, content: str) -> None:
        if self.api.is_available():
            try:
                if self.api.write_note(path, content):
                    return
            except:
                pass # Fallback to filesystem

        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_notes(self, folder: str) -> List[str]:
        # Always try API first for list_notes if available
        if self.api.is_available():
            try:
                return self.api.list_notes(folder)
            except:
                pass

        folder_path = self._get_full_path(folder)
        if not folder_path.exists():
            return []
        
        notes = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".md"):
                    full_file_path = Path(root) / file
                    notes.append(str(full_file_path.relative_to(self.vault_path)))
        return notes

    def note_exists(self, path: str) -> bool:
        return self._get_full_path(path).exists()
