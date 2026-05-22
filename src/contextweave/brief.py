"""
brief.py — Generate daily project brief (no LLM required).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from .db import get_conn, get_project_id
from .config import get_vault_path
from .graph import top_nodes


def generate_brief(project_slug: str) -> str:
    """
    Generate a structured daily brief as markdown.
    Queries: sessions from last 24h, observations count, latest handoff, top graph nodes.
    No LLM needed — purely data formatting.
    Returns the brief as a string.
    """
    project_id = get_project_id(project_slug)
    now = datetime.utcnow()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    date_str = now.strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        # Sessions in last 24h
        sessions = conn.execute(
            """
            SELECT id, agent, feature, status, summary, next_task, started_at, ended_at
            FROM sessions
            WHERE project_id = ?
              AND started_at >= ?
            ORDER BY started_at DESC
            """,
            (project_id, cutoff_24h),
        ).fetchall() if project_id else []

        # All-time last session
        last_session = conn.execute(
            """
            SELECT agent, feature, status, summary, next_task, started_at
            FROM sessions
            WHERE project_id = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone() if project_id else None

        # Observations in last 24h
        obs_count = conn.execute(
            """
            SELECT COUNT(*) AS n FROM observations
            WHERE project_id = ? AND created_at >= ?
            """,
            (project_id, cutoff_24h),
        ).fetchone()["n"] if project_id else 0

        # Latest handoff
        handoff = conn.execute(
            """
            SELECT from_agent, feature, summary, next_task, created_at
            FROM handoffs
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone() if project_id else None

        # Open questions from recent sessions
        open_questions = []
        for s in sessions:
            try:
                qs = json.loads(s["open_questions"] or "[]") if "open_questions" in s.keys() else []
                open_questions.extend(qs)
            except Exception:
                pass

        # Get open questions from all sessions table
        if project_id:
            q_rows = conn.execute(
                """
                SELECT open_questions FROM sessions
                WHERE project_id = ? AND started_at >= ?
                  AND open_questions IS NOT NULL
                """,
                (project_id, cutoff_24h),
            ).fetchall()
            for qr in q_rows:
                try:
                    qs = json.loads(qr["open_questions"] or "[]")
                    open_questions.extend(qs)
                except Exception:
                    pass
    finally:
        conn.close()

    # Top graph entities
    nodes = top_nodes(project_slug, limit=5)

    # Unique agents in recent sessions
    agents = list({s["agent"] for s in sessions if s["agent"]}) if sessions else []

    # Build the brief
    lines = [
        "---",
        f"project: {project_slug}",
        f"generated: {now.isoformat()}",
        "---",
        "",
        f"# Daily Brief — {project_slug} — {date_str}",
        "",
        "## Status",
    ]

    if last_session:
        time_ago = _time_ago(last_session["started_at"])
        lines.append(
            f"{last_session['agent']} was working on **{last_session['feature']}** · {time_ago}"
        )
        if handoff and handoff["next_task"]:
            lines.append(f"Next: {handoff['next_task']}")
    else:
        lines.append("No sessions recorded yet.")

    lines += [
        "",
        "## Activity (last 24h)",
        f"- {obs_count} observations captured",
        f"- {len(sessions)} sessions · agents: {', '.join(agents) or '—'}",
        "",
    ]

    if open_questions:
        lines.append("## Open Questions")
        seen_q: set[str] = set()
        for q in open_questions:
            if q and q not in seen_q:
                lines.append(f"- {q}")
                seen_q.add(q)
        lines.append("")

    if nodes:
        lines.append("## Top Context Nodes")
        for n in nodes:
            lines.append(f"- **{n['label']}** — mentioned {n['observation_count']}×")
        lines.append("")

    if handoff and handoff["next_task"]:
        lines += [
            "## Do This First",
            handoff["next_task"],
            "",
        ]

    brief_text = "\n".join(lines)

    # Write to vault if configured
    vault = get_vault_path(project_slug)
    if vault:
        try:
            brief_path = Path(vault) / "projects" / project_slug / f"BRIEF-{date_str}.md"
            brief_path.parent.mkdir(parents=True, exist_ok=True)
            brief_path.write_text(brief_text, encoding="utf-8")
        except Exception:
            pass

    return brief_text


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
