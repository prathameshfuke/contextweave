"""
consolidate.py — Hourly sweep: dedup, decay, prune orphans, export.
"""
from __future__ import annotations

from typing import Any, Dict

from .db import get_project_id
from .memory import consolidate as _memory_consolidate
from .graph import prune_orphans
from .config import get_vault_path
from .export import export_to_vault
from .db import get_conn, ensure_project
from .memory import observe


def run_sweep(project_slug: str) -> Dict[str, Any]:
    """
    Run the full consolidation sweep:
    1. memory.consolidate() — dedup + decay
    2. graph.prune_orphans() — delete zero-count nodes
    3. export.export_to_vault() — if vault configured
    4. Log sweep result as observation

    Returns sweep stats dict.
    """
    project_id = ensure_project(project_slug)

    stats = _memory_consolidate(project_slug)
    orphans = prune_orphans(project_id)

    exported = 0
    if get_vault_path(project_slug):
        try:
            exported = export_to_vault(project_slug)
        except Exception as e:
            exported = -1

    stats["orphans_pruned"] = orphans
    stats["vault_files_written"] = exported

    # Log sweep result to observations
    summary = (
        f"Consolidation sweep: merged={stats.get('merged', 0)}, "
        f"deleted={stats.get('deleted', 0)}, "
        f"decayed={stats.get('decayed', 0)}, "
        f"orphans={orphans}"
    )
    try:
        observe(project_slug, summary, source="system:consolidate")
    except Exception:
        pass

    return stats
