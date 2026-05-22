"""
db.py — SQLite data layer for contextweave v2.

Database lives at ~/.contextweave/cw.db.
Loads sqlite-vec extension on every connection.
Enables WAL mode for concurrent reads.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CW_DIR = Path.home() / ".contextweave"
DB_PATH = CW_DIR / "cw.db"


# ---------------------------------------------------------------------------
# sqlite-vec loader
# ---------------------------------------------------------------------------
def _load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Attempt to load the sqlite-vec extension. Returns True on success."""
    try:
        import sqlite_vec  # type: ignore
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    """Return a WAL-mode connection to ~/.contextweave/cw.db."""
    CW_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    _load_sqlite_vec(conn)
    return conn


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
_SCHEMA = """
-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY,
    slug        TEXT    UNIQUE NOT NULL,
    description TEXT,
    vault_path  TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Raw observations — everything captured automatically
CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY,
    project_id    INTEGER REFERENCES projects(id),
    content       TEXT    NOT NULL,
    source        TEXT,           -- 'hook:PostToolUse' | 'cli' | 'mcp' | 'import:jsonl'
    agent         TEXT,
    session_id    INTEGER,
    tags          TEXT,           -- JSON array as text
    created_at    TEXT    DEFAULT (datetime('now')),
    access_count  INTEGER DEFAULT 0,
    last_accessed TEXT
);

-- FTS5 index for BM25 search over observations
CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    content, tags,
    content='observations',
    content_rowid='id'
);

-- Triggers to keep FTS5 in sync with observations table
CREATE TRIGGER IF NOT EXISTS observations_ai
AFTER INSERT ON observations BEGIN
    INSERT INTO observations_fts(rowid, content, tags)
    VALUES (new.id, new.content, COALESCE(new.tags, '[]'));
END;

CREATE TRIGGER IF NOT EXISTS observations_ad
AFTER DELETE ON observations BEGIN
    INSERT INTO observations_fts(observations_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, COALESCE(old.tags, '[]'));
END;

CREATE TRIGGER IF NOT EXISTS observations_au
AFTER UPDATE ON observations BEGIN
    INSERT INTO observations_fts(observations_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, COALESCE(old.tags, '[]'));
    INSERT INTO observations_fts(rowid, content, tags)
    VALUES (new.id, new.content, COALESCE(new.tags, '[]'));
END;

-- Consolidated semantic memories (compressed from observations)
CREATE TABLE IF NOT EXISTS memories (
    id                   INTEGER PRIMARY KEY,
    project_id           INTEGER REFERENCES projects(id),
    content              TEXT    NOT NULL,
    source_observation_ids TEXT, -- JSON array of observation ids that were merged
    confidence           REAL    DEFAULT 1.0,
    decay_score          REAL    DEFAULT 1.0,
    created_at           TEXT    DEFAULT (datetime('now')),
    last_accessed        TEXT,
    access_count         INTEGER DEFAULT 0
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY,
    project_id     INTEGER REFERENCES projects(id),
    agent          TEXT    NOT NULL,
    feature        TEXT,
    status         TEXT    DEFAULT 'in-progress',
    summary        TEXT,
    next_task      TEXT,
    files_modified TEXT,   -- JSON array
    open_questions TEXT,   -- JSON array
    started_at     TEXT    DEFAULT (datetime('now')),
    ended_at       TEXT
);

-- Handoffs between agents
CREATE TABLE IF NOT EXISTS handoffs (
    id            INTEGER PRIMARY KEY,
    project_id    INTEGER REFERENCES projects(id),
    session_id    INTEGER REFERENCES sessions(id),
    from_agent    TEXT,
    feature       TEXT,
    summary       TEXT,
    next_task     TEXT,
    context_block TEXT,   -- full formatted markdown block ready to inject
    created_at    TEXT    DEFAULT (datetime('now'))
);

-- Knowledge graph — nodes
CREATE TABLE IF NOT EXISTS graph_nodes (
    id                INTEGER PRIMARY KEY,
    project_id        INTEGER REFERENCES projects(id),
    label             TEXT    NOT NULL,
    type              TEXT,   -- 'file' | 'decision' | 'feature' | 'entity' | 'agent'
    observation_count INTEGER DEFAULT 1,
    last_seen         TEXT    DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_nodes_project_label
    ON graph_nodes(project_id, label);

-- Knowledge graph — edges
CREATE TABLE IF NOT EXISTS graph_edges (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    source_id  INTEGER REFERENCES graph_nodes(id),
    target_id  INTEGER REFERENCES graph_nodes(id),
    weight     REAL    DEFAULT 1.0,
    last_seen  TEXT    DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_pair
    ON graph_edges(project_id, source_id, target_id);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_observations_project ON observations(project_id);
CREATE INDEX IF NOT EXISTS idx_observations_session ON observations(session_id);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_project ON handoffs(project_id);
"""

# sqlite-vec virtual table DDL — created separately after extension loads
_VEC_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS observation_vecs USING vec0(
    observation_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
"""


def init_db() -> None:
    """Create all tables and indexes. Safe to call multiple times (idempotent)."""
    conn = get_conn()
    try:
        conn.executescript(_SCHEMA)
        # Attempt to create the vec table only if sqlite-vec loaded
        try:
            conn.execute(_VEC_TABLE)
            conn.commit()
        except Exception:
            # sqlite-vec not available — skip vector table
            pass
        conn.commit()
    finally:
        conn.close()


def get_project_id(slug: str, conn: Optional[sqlite3.Connection] = None) -> Optional[int]:
    """Return the project id for a slug, or None if not found."""
    close = False
    if conn is None:
        conn = get_conn()
        close = True
    try:
        row = conn.execute(
            "SELECT id FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        if close:
            conn.close()


def ensure_project(slug: str, description: str = "", vault_path: str = "") -> int:
    """Ensure a project row exists and return its id."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO projects (slug, description, vault_path)
            VALUES (?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                description = COALESCE(NULLIF(excluded.description, ''), projects.description),
                vault_path  = COALESCE(NULLIF(excluded.vault_path, ''), projects.vault_path)
            """,
            (slug, description, vault_path),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
        return row["id"]
    finally:
        conn.close()


def vec_available() -> bool:
    """Return True if sqlite-vec extension loaded successfully."""
    conn = get_conn()
    try:
        conn.execute("SELECT vec_version()")
        return True
    except Exception:
        return False
    finally:
        conn.close()
