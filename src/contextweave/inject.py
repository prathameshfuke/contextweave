"""
inject.py — Write context blocks into agent config files.

All adapters use the marker pattern:
  <!-- CW:START --> ... <!-- CW:END -->

Replace between markers if they exist; append if not.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory import build_context_block
from .handoff import format_for_injection
from .config import ACTIVE_CONTEXT_FILE

_CW_START = "<!-- CW:START -->"
_CW_END = "<!-- CW:END -->"


def _build_block(project_slug: str, query: str = "") -> str:
    """Build the context block: memory search results + latest handoff."""
    ctx = build_context_block(project_slug, query or project_slug)
    handoff = format_for_injection(project_slug)
    if handoff:
        ctx += "\n---\n" + handoff
    return ctx


def _inject_into_file(path: Path, content: str) -> str:
    """
    Replace content between CW markers, or append if markers don't exist.
    Returns 'replaced' or 'appended'.
    """
    marked = f"{_CW_START}\n{content}\n{_CW_END}"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _CW_START in text and _CW_END in text:
            start = text.index(_CW_START)
            end = text.index(_CW_END) + len(_CW_END)
            new_text = text[:start] + marked + text[end:]
            path.write_text(new_text, encoding="utf-8")
            return "replaced"
        else:
            path.write_text(text + "\n\n" + marked + "\n", encoding="utf-8")
            return "appended"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marked + "\n", encoding="utf-8")
        return "created"


def write_claude_md(project_slug: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Inject context into CLAUDE.md in the project directory."""
    base = Path(cwd or ".").resolve()
    path = base / "CLAUDE.md"
    block = _build_block(project_slug)
    status = _inject_into_file(path, block)
    return {"adapter": "claude", "path": str(path), "status": status}


def write_cursorrules(project_slug: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Inject context into .cursorrules."""
    base = Path(cwd or ".").resolve()
    path = base / ".cursorrules"
    block = _build_block(project_slug)
    status = _inject_into_file(path, block)
    return {"adapter": "cursor", "path": str(path), "status": status}


def write_copilot(project_slug: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Inject context into .github/copilot-instructions.md."""
    base = Path(cwd or ".").resolve()
    path = base / ".github" / "copilot-instructions.md"
    block = _build_block(project_slug)
    status = _inject_into_file(path, block)
    return {"adapter": "copilot", "path": str(path), "status": status}


def write_gemini(project_slug: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Inject context into .gemini/system-prompt.md."""
    base = Path(cwd or ".").resolve()
    path = base / ".gemini" / "system-prompt.md"
    block = _build_block(project_slug)
    status = _inject_into_file(path, block)
    return {"adapter": "gemini", "path": str(path), "status": status}


def write_active_context(project_slug: str) -> Dict[str, Any]:
    """Write context to ~/.contextweave/active-context.md."""
    path = ACTIVE_CONTEXT_FILE
    block = _build_block(project_slug)
    status = _inject_into_file(path, block)
    return {"adapter": "active_context", "path": str(path), "status": status}


def inject_all(project_slug: str, cwd: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run all five injectors. Returns list of {adapter, path, status}."""
    results = []
    for fn in [write_claude_md, write_cursorrules, write_copilot, write_gemini]:
        try:
            results.append(fn(project_slug, cwd))
        except Exception as e:
            fname = getattr(fn, "__name__", "unknown")
            results.append({"adapter": fname, "path": "", "status": f"error: {e}"})
    try:
        results.append(write_active_context(project_slug))
    except Exception as e:
        results.append({"adapter": "active_context", "path": "", "status": f"error: {e}"})
    return results
