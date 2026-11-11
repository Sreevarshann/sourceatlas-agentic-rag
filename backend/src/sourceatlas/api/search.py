from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from sourceatlas.api.deps import DbSession
from sourceatlas.retrieval.search import Filters, search

router = APIRouter(tags=["search"])


class FiltersIn(BaseModel):
    collection_ids: list[str] = Field(default_factory=list, max_length=50)
    collections: list[str] = Field(default_factory=list, max_length=50)
    document_ids: list[str] = Field(default_factory=list, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)
    meta: dict[str, str] = Field(default_factory=dict)


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    method: Literal["vector", "keyword", "hybrid"] = "hybrid"
    k: int = Field(default=8, ge=1, le=50)
    min_score: float | None = None
    filters: FiltersIn = Field(default_factory=FiltersIn)


@router.post("/search")
def run_search(body: SearchIn, request: Request, db: DbSession) -> dict[str, Any]:
    res = search(
        db,
        request.app.state.embedder,
        body.query,
        method=body.method,
        k=body.k,
        filters=Filters(**body.filters.model_dump()),
        min_score=body.min_score,
    )
    return {
        "method": res.method,
        "timings_ms": res.timings_ms,
        "embedder": request.app.state.embedder.name,
        "hits": [asdict(h) for h in res.hits],
    }
