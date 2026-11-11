from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from sourceatlas.agent.service import evidence_graph, run_research
from sourceatlas.api.deps import DbSession
from sourceatlas.api.search import FiltersIn
from sourceatlas.db.models import ResearchSession
from sourceatlas.llm.base import LLMProvider
from sourceatlas.llm.factory import make_llm

router = APIRouter(prefix="/research", tags=["research"])


class ResearchIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    filters: FiltersIn = Field(default_factory=FiltersIn)
    parent_id: str | None = None


class SessionOut(BaseModel):
    id: str
    question: str
    parent_id: str | None
    status: str
    answer: dict[str, Any] | None
    evidence: list[Any]
    quarantined: list[Any]
    trace: list[Any]
    model_name: str | None
    embedder: str | None
    llm_usage: dict[str, Any]
    duration_ms: int | None
    created_at: datetime


def _llm(request: Request) -> LLMProvider:
    factory = getattr(request.app.state, "llm_factory", None)
    return factory() if factory else make_llm(request.app.state.settings)


def _out(rs: ResearchSession) -> SessionOut:
    return SessionOut.model_validate(rs, from_attributes=True)


@router.post("", response_model=SessionOut, status_code=201)
def research(body: ResearchIn, request: Request, db: DbSession) -> SessionOut:
    return _out(
        run_research(
            db,
            request.app.state.embedder,
            _llm(request),
            body.question,
            filters=body.filters.model_dump(),
            parent_id=body.parent_id,
        )
    )


@router.post("/stream", response_class=EventSourceResponse)
def research_stream(body: ResearchIn, request: Request) -> Iterator[dict[str, Any]]:
    """Streams the agent's real events: stages, retrieval calls, evidence, conflicts, answer."""
    llm, embedder, factory = _llm(request), request.app.state.embedder, request.app.state.sessionmaker
    q: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def work() -> None:
        with factory() as db:
            try:
                rs = run_research(
                    db,
                    embedder,
                    llm,
                    body.question,
                    filters=body.filters.model_dump(),
                    parent_id=body.parent_id,
                    on_event=q.put,
                )
                q.put({"type": "done", "session": _out(rs).model_dump(mode="json")})
            except Exception:
                q.put({"type": "error", "message": "Research failed unexpectedly."})
            finally:
                q.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (e := q.get()) is not None:
        yield e


@router.get("", response_model=list[SessionOut])
def history(db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[SessionOut]:
    return [
        _out(r)
        for r in db.scalars(select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(limit))
    ]


def _load(sid: str, db: DbSession) -> ResearchSession:
    rs = db.get(ResearchSession, sid)
    if rs is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return rs


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: DbSession) -> SessionOut:
    return _out(_load(session_id, db))


@router.get("/{session_id}/graph")
def graph(session_id: str, db: DbSession) -> dict[str, Any]:
    return evidence_graph(_load(session_id, db))
