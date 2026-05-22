"""
export.py — Obsidian vault export for contextweave v2.

Exports memories to Markdown files with YAML frontmatter.
Writes PROJECT.md index and GRAPH.md summary.
Optionally watches the SQLite DB for changes with watchdog.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import get_vault_path
from .db import get_conn, get_project_id


def export_to_vault(project_slug: str) -> int:
    """
    Export all memories for project_slug to the configured Obsidian vault.

    Writes:
      vault/projects/<slug>/memories/<id>.md   (one per memory)
      vault/projects/<slug>/PROJECT.md          (index with wikilinks)
      vault/projects/<slug>/GRAPH.md            (top entities)

    Returns count of files written.
    """
    vault_path = get_vault_path(project_slug)
    if not vault_path:
        return 0

    project_dir = Path(vault_path) / "projects" / project_slug
    memories_dir = project_dir / "memories"
    memories_dir.mkdir(parents=True, exist_ok=True)

    project_id = get_project_id(project_slug)
    if project_id is None:
        return 0

    conn = get_conn()
    written = 0
    memory_links = []

    try:
        memories = conn.execute(
            """
            SELECT id, content, source_observation_ids, confidence, decay_score,
                   created_at, access_count
            FROM memories
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        ).fetchall()

        for m in memories:
            fname = f"{m['id']}.md"
            fpath = memories_dir / fname
            tags = json.loads(m["source_observation_ids"] or "[]")
            frontmatter = (
                f"---\n"
                f"id: {m['id']}\n"
                f"source_observation_ids: {tags}\n"
                f"confidence: {m['confidence']}\n"
                f"decay_score: {m['decay_score']:.4f}\n"
                f"created_at: {m['created_at']}\n"
                f"access_count: {m['access_count']}\n"
                f"---\n\n"
            )
            fpath.write_text(frontmatter + m["content"] + "\n", encoding="utf-8")
            memory_links.append(f"[[memories/{m['id']}]]")
            written += 1

        # Write PROJECT.md index
        sessions = conn.execute(
            """
            SELECT id, agent, feature, status, started_at, ended_at
            FROM sessions
            WHERE project_id = ?
            ORDER BY started_at DESC
            LIMIT 20
            """,
            (project_id,),
        ).fetchall()

        session_lines = []
        for s in sessions:
            status_emoji = "🟢" if s["status"] == "completed" else "🟡"
            session_lines.append(f"- {status_emoji} **{s['agent']}** — {s['feature']} ({s['started_at'][:10]})")

        project_md = (
            f"# {project_slug}\n\n"
            f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n\n"
            f"## Memories ({len(memories)})\n\n"
            + "\n".join(memory_links or ["*(none)*"]) + "\n\n"
            f"## Sessions\n\n"
            + "\n".join(session_lines or ["*(none)*"]) + "\n"
        )
        (project_dir / "PROJECT.md").write_text(project_md, encoding="utf-8")
        written += 1

        # Write GRAPH.md
        from .graph import top_nodes
        nodes = top_nodes(project_slug, limit=20)
        graph_lines = [f"- **{n['label']}** ({n['type']}) — mentioned {n['observation_count']}×" for n in nodes]
        graph_md = (
            f"# Graph Summary — {project_slug}\n\n"
            f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n\n"
            f"## Top Entities\n\n"
            + "\n".join(graph_lines or ["*(none)*"]) + "\n"
        )
        (project_dir / "GRAPH.md").write_text(graph_md, encoding="utf-8")
        written += 1

        return written
    finally:
        conn.close()


def watch_and_export(project_slug: str, debounce_sec: float = 3.0) -> None:
    """
    Watch ~/.contextweave/cw.db for changes and re-export on every write.
    Runs indefinitely (blocking). Uses watchdog if available, falls back to polling.
    """
    from .db import DB_PATH

    try:
        from watchdog.observers import Observer  # type: ignore
        from watchdog.events import FileSystemEventHandler  # type: ignore

        _last_export = [0.0]

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory and "cw.db" in str(event.src_path):
                    now = time.time()
                    if now - _last_export[0] > debounce_sec:
                        _last_export[0] = now
                        try:
                            n = export_to_vault(project_slug)
                            print(f"[contextweave] Exported {n} files to vault")
                        except Exception as e:
                            print(f"[contextweave] Export error: {e}")

        observer = Observer()
        observer.schedule(_Handler(), str(DB_PATH.parent), recursive=False)
        observer.start()
        print(f"[contextweave] Watching {DB_PATH} — exporting on changes...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    except ImportError:
        # Polling fallback
        last_mtime = 0.0
        print(f"[contextweave] Polling {DB_PATH} every 5s (watchdog not available)...")
        while True:
            try:
                mtime = DB_PATH.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    time.sleep(debounce_sec)
                    try:
                        n = export_to_vault(project_slug)
                        print(f"[contextweave] Exported {n} files to vault")
                    except Exception as e:
                        print(f"[contextweave] Export error: {e}")
            except FileNotFoundError:
                pass
            time.sleep(5)
