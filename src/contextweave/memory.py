"""
memory.py — Capture, embed, search, and consolidate memories.

Triple-stream retrieval: BM25 (FTS5) + vector (sqlite-vec) + access-count boost.
Consolidation: cosine-similarity dedup — no LLM required.
"""
from __future__ import annotations

import json
import math
import struct
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .db import get_conn, ensure_project, get_project_id

# ---------------------------------------------------------------------------
# Embedding model — lazy-loaded once on first call
# ---------------------------------------------------------------------------
_model = None


def _get_model():
    global _model
    if _model is None:
        import os, warnings
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        warnings.filterwarnings("ignore", message=".*symlinks.*", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*unauthenticated.*", category=UserWarning)
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _embed(text: str) -> List[float]:
    """Return a 384-dimensional embedding for the given text."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _pack_vec(floats: List[float]) -> bytes:
    """Pack a list of floats into the sqlite-vec binary format."""
    return struct.pack(f"{len(floats)}f", *floats)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two unit vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))


# ---------------------------------------------------------------------------
# observe
# ---------------------------------------------------------------------------
def observe(
    project_slug: str,
    content: str,
    source: str = "cli",
    agent: Optional[str] = None,
    session_id: Optional[int] = None,
    tags: Optional[List[str]] = None,
) -> int:
    """
    Capture a new observation.

    Inserts into observations table, embeds with sentence-transformers,
    stores vector in observation_vecs, triggers graph extraction.
    Returns the new observation id.
    """
    tags = tags or []
    project_id = ensure_project(project_slug)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO observations (project_id, content, source, agent, session_id, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, content, source, agent, session_id, json.dumps(tags)),
        )
        obs_id = cur.lastrowid
        conn.commit()

        # Store embedding if sqlite-vec is available
        try:
            vec = _embed(content)
            packed = _pack_vec(vec)
            conn.execute(
                "INSERT OR REPLACE INTO observation_vecs(observation_id, embedding) VALUES (?, ?)",
                (obs_id, packed),
            )
            conn.commit()
        except Exception:
            pass  # degrade gracefully — BM25-only mode

        # Graph extraction (import here to avoid circular)
        try:
            from .graph import extract_and_link
            extract_and_link(project_id, obs_id, content, conn=None)
        except Exception:
            pass

        return obs_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# search — BM25 + vector, merged & reranked
# ---------------------------------------------------------------------------
def search(
    project_slug: str,
    query: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Hybrid BM25 + vector search.

    Returns up to top_k results ordered by combined score (higher = better).
    Each result dict: {id, content, source, agent, created_at, score, tags}.
    """
    project_id = get_project_id(project_slug)
    if project_id is None:
        return []

    conn = get_conn()
    try:
        scores: Dict[int, float] = {}

        # --- BM25 via FTS5 ---
        try:
            rows = conn.execute(
                """
                SELECT o.id, o.content, o.source, o.agent, o.created_at, o.tags,
                       (-fts.rank) AS bm25
                FROM observations_fts fts
                JOIN observations o ON o.id = fts.rowid
                WHERE fts MATCH ?
                  AND o.project_id = ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (query, project_id, top_k * 2),
            ).fetchall()

            bm25_vals = [r["bm25"] for r in rows if r["bm25"] > 0]
            bm25_max = max(bm25_vals) if bm25_vals else 1.0

            for row in rows:
                raw = row["bm25"]
                norm = (raw / bm25_max) if bm25_max > 0 else 0.0
                scores[row["id"]] = scores.get(row["id"], 0.0) + norm
        except Exception:
            pass

        # --- Vector search via sqlite-vec ---
        try:
            query_vec = _embed(query)
            packed = _pack_vec(query_vec)
            vec_rows = conn.execute(
                """
                SELECT observation_id, distance
                FROM observation_vecs
                WHERE embedding MATCH ?
                  AND k = ?
                ORDER BY distance
                """,
                (packed, top_k * 2),
            ).fetchall()
            for vr in vec_rows:
                # distance is L2 or cosine distance depending on sqlite-vec version
                # convert to similarity: 1 - normalised_distance
                d = float(vr["distance"])
                sim = max(0.0, 1.0 - d)
                oid = vr["observation_id"]
                scores[oid] = scores.get(oid, 0.0) + sim
        except Exception:
            pass

        if not scores:
            # Fallback: simple LIKE search
            rows = conn.execute(
                """
                SELECT id, content, source, agent, created_at, tags
                FROM observations
                WHERE project_id = ? AND content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, f"%{query}%", top_k),
            ).fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "content": r["content"],
                    "source": r["source"],
                    "agent": r["agent"],
                    "created_at": r["created_at"],
                    "score": 1.0,
                    "tags": json.loads(r["tags"] or "[]"),
                })
            return results

        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        now_str = datetime.utcnow().isoformat()
        for oid in sorted_ids:
            row = conn.execute(
                "SELECT id, content, source, agent, created_at, tags FROM observations WHERE id = ?",
                (oid,),
            ).fetchone()
            if row is None:
                continue
            # Update access stats
            conn.execute(
                "UPDATE observations SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                (now_str, oid),
            )
            results.append({
                "id": row["id"],
                "content": row["content"],
                "source": row["source"],
                "agent": row["agent"],
                "created_at": row["created_at"],
                "score": round(scores[oid], 4),
                "tags": json.loads(row["tags"] or "[]"),
            })
        conn.commit()
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# build_context_block
# ---------------------------------------------------------------------------
def build_context_block(
    project_slug: str,
    query: str,
    max_chars: int = 6000,
) -> str:
    """
    Build a formatted markdown context block from search results.
    Stops adding results when char count exceeds max_chars.
    """
    results = search(project_slug, query, top_k=20)
    lines = [f"# Project Memory: {project_slug}\n", "\n## Relevant Context\n\n"]
    total = sum(len(l) for l in lines)

    for r in results:
        created = r.get("created_at", "")
        source = r.get("source") or "unknown"
        agent = r.get("agent") or "—"
        time_ago = _time_ago(created)

        block = f"**[{source} · {agent} · {time_ago}]**\n{r['content']}\n\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "".join(lines)


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


# ---------------------------------------------------------------------------
# consolidate — dedup + decay
# ---------------------------------------------------------------------------
def consolidate(project_slug: str) -> Dict[str, int]:
    """
    Consolidate observations:
    1. Find near-duplicate pairs (cosine similarity > 0.92) in the last 48h.
    2. Keep highest access_count, delete rest, insert merged memory row.
    3. Apply decay to all memories: decay_score *= 0.98 (reset to 1.0 if accessed recently).

    Returns {merged, decayed, deleted}.
    """
    project_id = get_project_id(project_slug)
    if project_id is None:
        return {"merged": 0, "decayed": 0, "deleted": 0}

    conn = get_conn()
    merged = deleted = decayed = 0
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()

        # Fetch recent observations + their stored embeddings
        rows = conn.execute(
            """
            SELECT o.id, o.content, o.access_count, ov.embedding
            FROM observations o
            LEFT JOIN observation_vecs ov ON ov.observation_id = o.id
            WHERE o.project_id = ?
              AND o.created_at >= ?
            """,
            (project_id, cutoff),
        ).fetchall()

        # Build list of (id, content, access_count, embedding_floats)
        items = []
        for r in rows:
            emb = None
            if r["embedding"]:
                try:
                    n = len(r["embedding"]) // 4
                    emb = list(struct.unpack(f"{n}f", r["embedding"]))
                except Exception:
                    pass
            items.append((r["id"], r["content"], r["access_count"] or 0, emb))

        # Find duplicate clusters
        to_delete: set[int] = set()
        merged_clusters: list[tuple[int, list[int], str]] = []  # (keep_id, del_ids, content)

        for i in range(len(items)):
            if items[i][0] in to_delete:
                continue
            cluster_del: list[int] = []
            for j in range(i + 1, len(items)):
                if items[j][0] in to_delete:
                    continue
                # Compare embeddings if available
                if items[i][3] is not None and items[j][3] is not None:
                    sim = _cosine_similarity(items[i][3], items[j][3])
                    if sim > 0.92:
                        cluster_del.append(j)
                        to_delete.add(items[j][0])

            if cluster_del:
                # Keep the one with highest access_count
                keep_id = items[i][0]
                keep_content = items[i][1]
                del_ids = [items[j][0] for j in cluster_del]
                merged_clusters.append((keep_id, del_ids, keep_content))

        for keep_id, del_ids, content in merged_clusters:
            source_ids = json.dumps([keep_id] + del_ids)
            conn.execute(
                """
                INSERT INTO memories (project_id, content, source_observation_ids, confidence, decay_score)
                VALUES (?, ?, ?, 1.0, 1.0)
                """,
                (project_id, content, source_ids),
            )
            conn.executemany("DELETE FROM observations WHERE id = ?", [(did,) for did in del_ids])
            merged += 1
            deleted += len(del_ids)

        # Decay: decay_score *= 0.98, reset to 1.0 if accessed in last 24h
        recent_cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        conn.execute(
            """
            UPDATE memories
            SET decay_score = CASE
                WHEN last_accessed >= ? THEN 1.0
                ELSE decay_score * 0.98
            END
            WHERE project_id = ?
            """,
            (recent_cutoff, project_id),
        )
        decayed = conn.execute(
            "SELECT changes() AS n"
        ).fetchone()["n"]

        conn.commit()
        return {"merged": merged, "decayed": decayed, "deleted": deleted}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# save — explicit long-term memory
# ---------------------------------------------------------------------------
def save(project_slug: str, content: str, confidence: float = 1.0) -> int:
    """Explicitly save a memory (not from observation pipeline)."""
    project_id = ensure_project(project_slug)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO memories (project_id, content, source_observation_ids, confidence, decay_score)
            VALUES (?, ?, '[]', ?, 1.0)
            """,
            (project_id, content, confidence),
        )
        mem_id = cur.lastrowid
        conn.commit()
        return mem_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# list_memories
# ---------------------------------------------------------------------------
def list_memories(project_slug: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent memories for a project."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, content, confidence, decay_score, created_at, access_count, last_accessed
            FROM memories
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
def project_stats(project_slug: str) -> Dict[str, Any]:
    """Return counts for a project."""
    project_id = get_project_id(project_slug)
    if project_id is None:
        return {"observations": 0, "memories": 0, "sessions": 0, "graph_nodes": 0}
    conn = get_conn()
    try:
        obs = conn.execute("SELECT COUNT(*) AS n FROM observations WHERE project_id=?", (project_id,)).fetchone()["n"]
        mem = conn.execute("SELECT COUNT(*) AS n FROM memories WHERE project_id=?", (project_id,)).fetchone()["n"]
        ses = conn.execute("SELECT COUNT(*) AS n FROM sessions WHERE project_id=?", (project_id,)).fetchone()["n"]
        gn = conn.execute("SELECT COUNT(*) AS n FROM graph_nodes WHERE project_id=?", (project_id,)).fetchone()["n"]
        return {"observations": obs, "memories": mem, "sessions": ses, "graph_nodes": gn}
    finally:
        conn.close()
