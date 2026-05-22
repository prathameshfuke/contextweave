"""
session.py — Session lifecycle management (SQLite-backed, v2).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import get_conn, ensure_project, get_project_id
from .memory import observe


def start_session(
    project_slug: str,
    agent: str,
    feature: str,
) -> int:
    """
    Start a new session.
    Inserts a sessions row, observes 'Session started: {feature}'.
    Returns the session id.
    """
    project_id = ensure_project(project_slug)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO sessions (project_id, agent, feature, status, started_at)
            VALUES (?, ?, ?, 'in-progress', datetime('now'))
            """,
            (project_id, agent, feature),
        )
        session_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    observe(
        project_slug,
        f"Session started: {feature} (agent={agent})",
        source="hook:SessionStart",
        agent=agent,
        session_id=session_id,
    )

    # Print the last handoff if one exists
    try:
        from .handoff import format_for_injection, get_latest
        h = get_latest(project_slug)
        if h:
            from rich.console import Console
            from rich.panel import Panel
            console = Console(highlight=False)
            content = format_for_injection(project_slug)
            console.print(Panel(
                content,
                title="[bold yellow]Previous Session Handoff[/bold yellow]",
                border_style="yellow",
            ))
    except Exception:
        pass

    return session_id


def close_session(
    project_slug: str,
    session_id: int,
    summary: str,
    next_task: str,
    files_modified: Optional[List[str]] = None,
    open_questions: Optional[List[str]] = None,
) -> None:
    """
    Close a session, generate a handoff, and observe the summary.
    """
    files_modified = files_modified or []
    open_questions = open_questions or []

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT agent, feature FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return
        agent = row["agent"]
        feature = row["feature"]

        conn.execute(
            """
            UPDATE sessions
            SET status = 'completed',
                summary = ?,
                next_task = ?,
                files_modified = ?,
                open_questions = ?,
                ended_at = datetime('now')
            WHERE id = ?
            """,
            (
                summary,
                next_task,
                json.dumps(files_modified),
                json.dumps(open_questions),
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    observe(
        project_slug,
        f"Session completed: {summary}",
        source="hook:SessionEnd",
        agent=agent,
        session_id=session_id,
    )

    # Generate handoff
    from .handoff import generate as _gen_handoff
    _gen_handoff(project_slug, session_id)


def get_last_session(project_slug: str) -> Optional[Dict[str, Any]]:
    """Return the most recent session row as a dict."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, agent, feature, status, summary, next_task,
                   files_modified, open_questions, started_at, ended_at
            FROM sessions
            WHERE project_id = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["files_modified"] = json.loads(d["files_modified"] or "[]")
        d["open_questions"] = json.loads(d["open_questions"] or "[]")
        return d
    finally:
        conn.close()


def list_sessions(project_slug: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent sessions with stats."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.agent, s.feature, s.status, s.summary, s.next_task,
                   s.files_modified, s.open_questions, s.started_at, s.ended_at,
                   COUNT(o.id) AS observation_count
            FROM sessions s
            LEFT JOIN observations o ON o.session_id = s.id
            WHERE s.project_id = ?
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["files_modified"] = json.loads(d.get("files_modified") or "[]")
            d["open_questions"] = json.loads(d.get("open_questions") or "[]")
            result.append(d)
        return result
    finally:
        conn.close()
