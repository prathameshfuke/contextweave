"""
graph.py — Knowledge graph extraction and traversal.

Extracts entities from observation text using regex patterns.
Stores in graph_nodes / graph_edges with UPSERT semantics.
Builds D3-compatible JSON for the viewer.
"""
from __future__ import annotations

import re
import sqlite3
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from .db import get_conn, get_project_id

# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------
_FILE_PATH_RE = re.compile(r'\b[\w\-/\\\.]+\.(?:py|ts|tsx|js|jsx|json|md|txt|yml|yaml|toml|cfg|ini|sh|bat|css|html|sql|rs|go|java|kt|rb|php|c|cpp|h)\b')
_DECISION_RE = re.compile(r'(?:^|\.\s+)(decided\s+.+?|chose\s+.+?|using\s+.+?|switched\s+to\s+.+?)(?:\.|$)', re.IGNORECASE | re.MULTILINE)
_FEATURE_RE = re.compile(r'(?:^|\.\s+)(working\s+on\s+.+?|implementing\s+.+?|building\s+.+?|adding\s+.+?)(?:\.|$)', re.IGNORECASE | re.MULTILINE)


def _extract_entities(content: str) -> List[Tuple[str, str]]:
    """
    Extract (label, type) pairs from content text.
    Types: 'file', 'decision', 'feature'
    """
    entities: List[Tuple[str, str]] = []

    for m in _FILE_PATH_RE.findall(content):
        label = m.strip()
        if len(label) > 2 and len(label) < 200:
            entities.append((label, "file"))

    for m in _DECISION_RE.findall(content):
        label = m.strip()[:120]
        if label:
            entities.append((label, "decision"))

    for m in _FEATURE_RE.findall(content):
        label = m.strip()[:120]
        if label:
            entities.append((label, "feature"))

    # Deduplicate by label
    seen: Set[str] = set()
    result = []
    for label, typ in entities:
        if label not in seen:
            seen.add(label)
            result.append((label, typ))
    return result


# ---------------------------------------------------------------------------
# extract_and_link
# ---------------------------------------------------------------------------
def extract_and_link(
    project_id: int,
    obs_id: int,
    content: str,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """
    Extract entities from content and UPSERT into graph_nodes.
    For each pair of entities co-occurring in the same observation, UPSERT a graph_edge.
    """
    entities = _extract_entities(content)
    if not entities:
        return

    close = False
    if conn is None:
        conn = get_conn()
        close = True

    try:
        node_ids: List[int] = []
        for label, etype in entities:
            # UPSERT node
            conn.execute(
                """
                INSERT INTO graph_nodes (project_id, label, type, observation_count, last_seen)
                VALUES (?, ?, ?, 1, datetime('now'))
                ON CONFLICT(project_id, label) DO UPDATE SET
                    observation_count = observation_count + 1,
                    last_seen = datetime('now'),
                    type = COALESCE(type, excluded.type)
                """,
                (project_id, label, etype),
            )
            row = conn.execute(
                "SELECT id FROM graph_nodes WHERE project_id = ? AND label = ?",
                (project_id, label),
            ).fetchone()
            if row:
                node_ids.append(row["id"])

        # UPSERT edges for all pairs
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                src, tgt = sorted([node_ids[i], node_ids[j]])
                conn.execute(
                    """
                    INSERT INTO graph_edges (project_id, source_id, target_id, weight, last_seen)
                    VALUES (?, ?, ?, 1.0, datetime('now'))
                    ON CONFLICT(project_id, source_id, target_id) DO UPDATE SET
                        weight = weight + 1.0,
                        last_seen = datetime('now')
                    """,
                    (project_id, src, tgt),
                )
        conn.commit()
    finally:
        if close:
            conn.close()


# ---------------------------------------------------------------------------
# build_graph_json — D3-compatible output
# ---------------------------------------------------------------------------
def build_graph_json(project_slug: str) -> Dict[str, Any]:
    """
    Return a D3 force-directed graph dict:
    {
      "nodes": [{"id": 1, "label": "src/auth.ts", "type": "file", "size": 12}],
      "links": [{"source": 1, "target": 2, "weight": 3.0}]
    }
    """
    project_id = get_project_id(project_slug)
    if project_id is None:
        return {"nodes": [], "links": []}

    conn = get_conn()
    try:
        node_rows = conn.execute(
            """
            SELECT id, label, type, observation_count
            FROM graph_nodes
            WHERE project_id = ?
            ORDER BY observation_count DESC
            LIMIT 200
            """,
            (project_id,),
        ).fetchall()

        node_ids = {r["id"] for r in node_rows}
        nodes = [
            {
                "id": r["id"],
                "label": r["label"],
                "type": r["type"] or "entity",
                "size": max(5, min(40, r["observation_count"] * 3)),
            }
            for r in node_rows
        ]

        edge_rows = conn.execute(
            """
            SELECT source_id, target_id, weight
            FROM graph_edges
            WHERE project_id = ?
              AND source_id IN ({ph})
              AND target_id IN ({ph})
            ORDER BY weight DESC
            LIMIT 500
            """.format(ph=",".join("?" * len(node_ids))),
            [project_id] + list(node_ids) + list(node_ids),
        ).fetchall() if node_ids else []

        links = [
            {"source": r["source_id"], "target": r["target_id"], "weight": r["weight"]}
            for r in edge_rows
        ]

        return {"nodes": nodes, "links": links}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# query_entity — BFS subgraph
# ---------------------------------------------------------------------------
def query_entity(project_slug: str, entity_label: str, depth: int = 2) -> Dict[str, Any]:
    """BFS from a matching node, return subgraph dict."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return {"nodes": [], "links": []}

    conn = get_conn()
    try:
        start = conn.execute(
            "SELECT id, label, type, observation_count FROM graph_nodes WHERE project_id = ? AND label LIKE ?",
            (project_id, f"%{entity_label}%"),
        ).fetchone()
        if not start:
            return {"nodes": [], "links": []}

        visited: Set[int] = set()
        queue: deque[Tuple[int, int]] = deque([(start["id"], 0)])
        nodes: List[Dict] = []
        links: List[Dict] = []

        while queue:
            nid, d = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            row = conn.execute(
                "SELECT id, label, type, observation_count FROM graph_nodes WHERE id = ?",
                (nid,),
            ).fetchone()
            if row:
                nodes.append({
                    "id": row["id"],
                    "label": row["label"],
                    "type": row["type"] or "entity",
                    "size": max(5, min(40, row["observation_count"] * 3)),
                })

            if d < depth:
                edges = conn.execute(
                    """
                    SELECT source_id, target_id, weight FROM graph_edges
                    WHERE project_id = ? AND (source_id = ? OR target_id = ?)
                    """,
                    (project_id, nid, nid),
                ).fetchall()
                for e in edges:
                    links.append({"source": e["source_id"], "target": e["target_id"], "weight": e["weight"]})
                    neighbor = e["target_id"] if e["source_id"] == nid else e["source_id"]
                    if neighbor not in visited:
                        queue.append((neighbor, d + 1))

        return {"nodes": nodes, "links": links}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# prune_orphans
# ---------------------------------------------------------------------------
def prune_orphans(project_id: int) -> int:
    """Delete graph nodes with observation_count = 0. Returns count deleted."""
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM graph_nodes WHERE project_id = ? AND observation_count = 0",
            (project_id,),
        )
        n = conn.execute("SELECT changes() AS n").fetchone()["n"]
        conn.commit()
        return n
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# top_nodes helper for brief.py
# ---------------------------------------------------------------------------
def top_nodes(project_slug: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return the top N graph nodes by observation_count."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT label, type, observation_count
            FROM graph_nodes
            WHERE project_id = ?
            ORDER BY observation_count DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
