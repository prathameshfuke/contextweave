"""
config.py — Configuration for contextweave v2.

No Obsidian vault required at startup.
Reads from ~/.contextweave/config.toml (auto-created on first use).
Also reads CONTEXTWEAVE_PROJECT from environment / .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env from current directory (if present)
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CW_DIR = Path.home() / ".contextweave"
CONFIG_FILE = CW_DIR / "config.toml"
DB_PATH = CW_DIR / "cw.db"
ACTIVE_CONTEXT_FILE = CW_DIR / "active-context.md"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    "db_path": str(DB_PATH),
    "vault_path": "",          # optional Obsidian vault
    "default_project": "",     # set via CONTEXTWEAVE_PROJECT env var
    "viewer_port": 4222,
    "embed_model": "all-MiniLM-L6-v2",
    "max_context_chars": 6000,
}


class ConfigError(RuntimeError):
    """Raised when contextweave configuration is invalid."""


# ---------------------------------------------------------------------------
# Simple TOML reader/writer (no external dep — TOML is stdlib in Python 3.11+)
# ---------------------------------------------------------------------------
def _read_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib  # type: ignore  # Python 3.11+
        with open(path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        # fallback: manual parse (only top-level key=value pairs)
        cfg: Dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            cfg[k] = v
        return cfg


def _write_toml(path: Path, data: Dict[str, Any]) -> None:
    lines = ["# contextweave configuration\n"]
    for k, v in data.items():
        if isinstance(v, str):
            lines.append(f'{k} = "{v}"\n')
        elif isinstance(v, bool):
            lines.append(f'{k} = {"true" if v else "false"}\n')
        else:
            lines.append(f"{k} = {v}\n")
    path.write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    """Load config, falling back to defaults. Never raises on missing file."""
    CW_DIR.mkdir(parents=True, exist_ok=True)
    cfg = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        try:
            cfg.update(_read_toml(CONFIG_FILE))
        except Exception:
            pass  # silently use defaults if TOML is invalid
    # Environment overrides
    if os.getenv("CONTEXTWEAVE_PROJECT"):
        cfg["default_project"] = os.getenv("CONTEXTWEAVE_PROJECT", "")
    if os.getenv("CONTEXTWEAVE_VAULT"):
        cfg["vault_path"] = os.getenv("CONTEXTWEAVE_VAULT", "")
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    CW_DIR.mkdir(parents=True, exist_ok=True)
    _write_toml(CONFIG_FILE, cfg)


def get_vault_path(project_slug: Optional[str] = None) -> Optional[str]:
    """Return configured vault path for a project or the global default."""
    from . import db as _db

    if project_slug:
        conn = _db.get_conn()
        try:
            row = conn.execute(
                "SELECT vault_path FROM projects WHERE slug = ?", (project_slug,)
            ).fetchone()
            if row and row["vault_path"]:
                return row["vault_path"]
        finally:
            conn.close()

    cfg = load_config()
    vp = cfg.get("vault_path", "")
    return vp if vp else None


def get_default_project() -> str:
    return os.getenv("CONTEXTWEAVE_PROJECT") or load_config().get("default_project", "")
