"""
viewer/app.py — FastAPI web viewer for contextweave v2.

Runs on port 4222.
Endpoints:
  GET /                         → serve index.html
  GET /api/graph?project=<slug> → D3 graph JSON
  GET /api/memories?project=<slug>&q=<query>
  GET /api/sessions?project=<slug>
  GET /api/status               → global stats
  GET /api/brief?project=<slug>
  GET /api/stream               → SSE live observation feed
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ContextWeave Viewer", version="0.2.0")

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Root — serve index.html
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    if _INDEX_HTML.exists():
        return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ContextWeave viewer not found</h1>", status_code=404)


# ---------------------------------------------------------------------------
# /api/graph
# ---------------------------------------------------------------------------
@app.get("/api/graph")
async def api_graph(project: str = ""):
    if not project:
        return JSONResponse({"nodes": [], "links": []})
    from contextweave.graph import build_graph_json  # type: ignore
    data = build_graph_json(project)
    return JSONResponse(data)


# ---------------------------------------------------------------------------
# /api/memories
# ---------------------------------------------------------------------------
@app.get("/api/memories")
async def api_memories(project: str = "", q: str = "", limit: int = 50):
    if not project:
        return JSONResponse([])
    if q:
        from contextweave.memory import search  # type: ignore
        results = search(project, q, top_k=limit)
    else:
        from contextweave.memory import list_memories  # type: ignore
        results = list_memories(project, limit=limit)
    return JSONResponse(results)


# ---------------------------------------------------------------------------
# /api/sessions
# ---------------------------------------------------------------------------
@app.get("/api/sessions")
async def api_sessions(project: str = "", limit: int = 20):
    if not project:
        return JSONResponse([])
    from contextweave.session import list_sessions  # type: ignore
    sessions = list_sessions(project, limit=limit)
    return JSONResponse(sessions)


# ---------------------------------------------------------------------------
# /api/status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def api_status():
    from contextweave.db import get_conn, DB_PATH  # type: ignore
    conn = get_conn()
    try:
        projects = conn.execute("SELECT slug FROM projects").fetchall()
        total_obs = conn.execute("SELECT COUNT(*) AS n FROM observations").fetchone()["n"]
        total_mem = conn.execute("SELECT COUNT(*) AS n FROM memories").fetchone()["n"]
    except Exception:
        projects = []
        total_obs = 0
        total_mem = 0
    finally:
        if conn:
            conn.close()

    db_size = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0

    return JSONResponse({
        "projects": [r["slug"] for r in projects],
        "total_observations": total_obs,
        "total_memories": total_mem,
        "db_size_mb": round(db_size, 2),
    })


# ---------------------------------------------------------------------------
# /api/brief
# ---------------------------------------------------------------------------
@app.get("/api/brief")
async def api_brief(project: str = ""):
    if not project:
        return JSONResponse({"error": "project required"})
    from contextweave.brief import generate_brief  # type: ignore
    brief = generate_brief(project)
    return JSONResponse({"brief": brief})


# ---------------------------------------------------------------------------
# /api/stream — Server-Sent Events live feed
# ---------------------------------------------------------------------------
@app.get("/api/stream")
async def api_stream(project: str = ""):
    async def event_generator() -> AsyncGenerator[str, None]:
        from contextweave.db import get_conn  # type: ignore
        from contextweave.db import get_project_id  # type: ignore

        # Query MAX(id) on connection to establish client-local last_obs_id
        last_obs_id = 0
        try:
            conn = get_conn()
            row = conn.execute("SELECT MAX(id) AS max_id FROM observations").fetchone()
            if row and row["max_id"] is not None:
                last_obs_id = row["max_id"]
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Send initial connection event
        yield "data: {\"type\":\"connected\"}\n\n"

        while True:
            try:
                conn = get_conn()
                try:
                    query = """
                        SELECT o.id, o.content, o.source, o.agent, o.created_at, o.tags
                        FROM observations o
                    """
                    params = []
                    if project:
                        pid = get_project_id(project, conn)
                        if pid:
                            query += " WHERE o.project_id = ? AND o.id > ?"
                            params = [pid, last_obs_id]
                        else:
                            query += " WHERE o.id > ?"
                            params = [last_obs_id]
                    else:
                        query += " WHERE o.id > ?"
                        params = [last_obs_id]
                    query += " ORDER BY o.id ASC LIMIT 20"

                    rows = conn.execute(query, params).fetchall()
                finally:
                    conn.close()

                for row in rows:
                    last_obs_id = max(last_obs_id, row["id"])
                    event_data = {
                        "id": row["id"],
                        "content": row["content"],
                        "source": row["source"],
                        "agent": row["agent"],
                        "created_at": row["created_at"],
                        "tags": json.loads(row["tags"] or "[]"),
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

            except Exception:
                pass

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------
def run(port: int = 4222):
    import uvicorn  # type: ignore
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
