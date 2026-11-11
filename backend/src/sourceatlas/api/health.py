from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from sourceatlas import __version__

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    s = request.app.state.settings
    db_ok, vector = False, None
    try:
        with request.app.state.engine.connect() as c:
            vector = c.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
            db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "database": db_ok,
        "pgvector": vector,
        "llm_provider": s.llm_provider,
        "embedding_provider": s.embedding_provider,
        "embedding_model": s.embedding_model,
    }
