"""
handoff.py — Agent-to-agent context transfer.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import get_conn, get_project_id, ensure_project
from .memory import build_context_block


def generate(project_slug: str, session_id: int) -> Optional[int]:
    """
    Read session row, build context_block markdown, insert handoffs row.
    Returns the handoff id.
    """
    project_id = ensure_project(project_slug)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT agent, feature, summary, next_task, open_questions
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None

        agent = row["agent"] or "unknown"
        feature = row["feature"] or ""
        summary = row["summary"] or ""
        next_task = row["next_task"] or ""
        questions = json.loads(row["open_questions"] or "[]")

        context_block = format_for_injection_raw(agent, feature, summary, next_task, questions)
        # Append relevant project memory context to the handoff block
        mem_block = build_context_block(project_slug, next_task or feature or summary)
        if mem_block:
            context_block += "\n\n" + mem_block

        cur = conn.execute(
            """
            INSERT INTO handoffs (project_id, session_id, from_agent, feature, summary, next_task, context_block)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, session_id, agent, feature, summary, next_task, context_block),
        )
        handoff_id = cur.lastrowid
        conn.commit()
        return handoff_id
    finally:
        conn.close()


def get_latest(project_slug: str) -> Optional[Dict[str, Any]]:
    """Return the most recent handoff row."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, from_agent, feature, summary, next_task, context_block, created_at
            FROM handoffs
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def format_for_injection(project_slug: str) -> str:
    """Return a formatted handoff markdown block for injection."""
    h = get_latest(project_slug)
    if not h:
        return "No previous handoff — fresh project"
    time_ago = _time_ago(h.get("created_at", ""))
    lines = [
        f"## Handoff from {h['from_agent']} — {time_ago}",
        f"**Feature:** {h['feature']}",
        f"**Next step:** {h['next_task']}",
        f"**Summary:** {h['summary']}",
    ]
    return "\n".join(lines)


def format_for_injection_raw(
    agent: str,
    feature: str,
    summary: str,
    next_task: str,
    open_questions: Optional[List[str]] = None,
) -> str:
    """Build the handoff markdown block from raw fields."""
    lines = [
        f"## Handoff from {agent}",
        f"**Feature:** {feature}",
        f"**Next step:** {next_task}",
        f"**Summary:** {summary}",
    ]
    if open_questions:
        lines.append("\n**Open Questions:**")
        for q in open_questions:
            lines.append(f"- {q}")
    return "\n".join(lines)


def _time_ago(iso_str: str) -> str:
    if not iso_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_str)
        diff = datetime.utcnow() - dt
        s = int(diff.total_seconds())
        if s < 60:
            return f"{s}s ago"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return "unknown"
