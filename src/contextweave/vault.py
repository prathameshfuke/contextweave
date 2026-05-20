from pathlib import Path
from typing import List, Optional
import os
from .vault_api import VaultAPI
from .config import load_config

class VaultError(RuntimeError):
    """Raised when a vault operation cannot be completed."""

class Vault:
    def __init__(self, vault_path: str):
        if not isinstance(vault_path, str) or not vault_path.strip():
            raise VaultError("Vault path is not configured.")

        self.vault_path = Path(vault_path).expanduser().resolve()
        if not self.vault_path.exists():
            raise VaultError(f"Vault path does not exist: {self.vault_path}")
        if not self.vault_path.is_dir():
            raise VaultError(f"Vault path is not a directory: {self.vault_path}")
        
        config = load_config()
        self.api = VaultAPI(config.get("obsidian_api_key", ""), config.get("obsidian_port", 27123))
        self._api_available = None

    def _api_is_available(self) -> bool:
        if self._api_available is None:
            self._api_available = self.api.is_available()
        return self._api_available

    def _get_full_path(self, relative_path: str) -> Path:
        full_path = (self.vault_path / relative_path).resolve()
        try:
            full_path.relative_to(self.vault_path)
        except ValueError as e:
            raise VaultError(f"Path escapes configured vault: {relative_path}") from e
        return full_path

    def read_note(self, path: str) -> str:
        if self._api_is_available():
            try:
                return self.api.read_note(path)
            except Exception:
                pass  # Fallback to filesystem
        
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise VaultError(f"Note not found: {path}")
        if not full_path.is_file():
            raise VaultError(f"Note path is not a file: {path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError as e:
            raise VaultError(f"Permission denied reading note: {path}") from e
        except UnicodeDecodeError as e:
            raise VaultError(f"Note is not valid UTF-8: {path}") from e
        except OSError as e:
            raise VaultError(f"Could not read note {path}: {e}") from e

    def write_note(self, path: str, content: str) -> None:
        if self._api_is_available():
            try:
                if self.api.write_note(path, content):
                    return
            except Exception:
                pass  # Fallback to filesystem

        full_path = self._get_full_path(path)
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
        except PermissionError as e:
            raise VaultError(f"Permission denied writing note: {path}") from e
        except OSError as e:
            raise VaultError(f"Could not write note {path}: {e}") from e

    def list_notes(self, folder: str) -> List[str]:
        # Always try API first for list_notes if available
        if self._api_is_available():
            try:
                return self.api.list_notes(folder)
            except Exception:
                pass

        folder_path = self._get_full_path(folder)
        if not folder_path.exists():
            return []
        if not folder_path.is_dir():
            raise VaultError(f"Note folder path is not a directory: {folder}")
        
        notes = []
        try:
            errors = []
            for root, _, files in os.walk(folder_path, onerror=errors.append):
                for file in files:
                    if file.endswith(".md"):
                        full_file_path = Path(root) / file
                        notes.append(str(full_file_path.relative_to(self.vault_path)))
            if errors:
                raise errors[0]
        except PermissionError as e:
            raise VaultError(f"Permission denied listing notes in: {folder}") from e
        except OSError as e:
            raise VaultError(f"Could not list notes in {folder}: {e}") from e
        return notes

    def note_exists(self, path: str) -> bool:
        return self._get_full_path(path).exists()
