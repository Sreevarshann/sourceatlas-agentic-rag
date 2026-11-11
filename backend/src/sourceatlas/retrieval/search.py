"""Hybrid retrieval over one PostgreSQL database.

* ``vector``  — pgvector cosine distance on the HNSW index.
* ``keyword`` — Postgres full-text search (``websearch_to_tsquery`` + ``ts_rank_cd``).
* ``hybrid``  — reciprocal rank fusion (RRF, k=60) of the two ranked lists. RRF uses only
  ranks, so it needs no score calibration between cosine similarity and ts_rank.

All queries are parameterised SQLAlchemy Core; filters restrict by collection, document,
tag and exact-match metadata keys. Only passages of each document's *current ready*
version are searchable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.orm import Session

from sourceatlas.db.models import Collection, Document, DocumentVersion, Passage
from sourceatlas.embed.providers import Embedder

Method = Literal["vector", "keyword", "hybrid"]
RRF_K = 60


@dataclass
class Filters:
    collection_ids: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)  # names
    document_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class Hit:
    passage_id: str
    document_id: str
    version_id: str
    document_title: str
    collection: str
    version: int
    page: int | None
    section: str | None
    text: str
    ordinal: int
    score: float
    ranks: dict[str, int] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    source_uri: str | None = None


def _current_versions() -> Any:
    """Subquery: latest ready version id per document."""
    ranked = (
        select(
            DocumentVersion.id.label("vid"),
            func.row_number()
            .over(partition_by=DocumentVersion.document_id, order_by=DocumentVersion.version.desc())
            .label("rn"),
        )
        .where(DocumentVersion.status == "ready")
        .subquery()
    )
    return select(ranked.c.vid).where(ranked.c.rn == 1)


def _base(filters: Filters) -> Any:
    stmt = (
        select(
            Passage,
            Document.title,
            Document.meta,
            Document.source_uri,
            Collection.name,
            DocumentVersion.version,
        )
        .join(Document, Document.id == Passage.document_id)
        .join(Collection, Collection.id == Passage.collection_id)
        .join(DocumentVersion, DocumentVersion.id == Passage.version_id)
        .where(Passage.version_id.in_(_current_versions()))
    )
    conds: list[Any] = []
    if filters.collection_ids:
        conds.append(Passage.collection_id.in_(filters.collection_ids))
    if filters.collections:
        conds.append(Collection.name.in_(filters.collections))
    if filters.document_ids:
        conds.append(Passage.document_id.in_(filters.document_ids))
    for t in filters.tags:
        conds.append(Document.tags.contains([t]))
    for k, v in filters.meta.items():
        conds.append(Document.meta[k].astext == str(v))
    return stmt.where(and_(*conds)) if conds else stmt


def _hit(row: Any, score: float) -> Hit:
    p, title, meta, uri, coll, version = row
    return Hit(
        p.id,
        p.document_id,
        p.version_id,
        title,
        coll,
        version,
        p.page,
        p.section,
        p.text,
        p.ordinal,
        score,
        meta=dict(meta or {}),
        source_uri=uri,
    )


def vector_search(db: Session, embedder: Embedder, query: str, k: int, filters: Filters) -> list[Hit]:
    qv = embedder.embed_query(query)
    dist = Passage.embedding.cosine_distance(qv)
    rows = db.execute(
        _base(filters)
        .add_columns(dist.label("d"))
        .where(Passage.embedding.is_not(None))
        .order_by(dist)
        .limit(k)
    ).all()
    out = []
    for r in rows:
        h = _hit(r[:-1], 1.0 - float(r[-1]))
        h.scores["vector"] = h.score
        out.append(h)
    return out


def keyword_search(db: Session, query: str, k: int, filters: Filters) -> list[Hit]:
    """Terms are OR-ed so partially matching passages still rank (phrases are kept;
    ``-term`` exclusions are not supported in this mode)."""
    if not db.execute(select(func.numnode(func.websearch_to_tsquery("english", query)))).scalar():
        return []  # stop-words only
    tsq = func.websearch_to_tsquery("english", query)
    # OR the query terms so partial matches still rank (websearch syntax defaults to AND)
    or_q = func.to_tsquery(
        "english",
        func.array_to_string(
            func.regexp_split_to_array(func.trim(func.querytree(tsq)), literal_column("' & '")), " | "
        ),
    )
    rank = func.ts_rank_cd(Passage.tsv, or_q, 32)
    rows = db.execute(
        _base(filters)
        .add_columns(rank.label("r"))
        .where(Passage.tsv.op("@@")(or_q))
        .order_by(rank.desc(), Passage.ordinal)
        .limit(k)
    ).all()
    out = []
    for r in rows:
        h = _hit(r[:-1], float(r[-1]))
        h.scores["keyword"] = h.score
        out.append(h)
    return out


def rrf(lists: dict[str, list[Hit]], k: int) -> list[Hit]:
    fused: dict[str, Hit] = {}
    for method, hits in lists.items():
        for rank, h in enumerate(hits, start=1):
            cur = fused.setdefault(h.passage_id, h)
            cur.ranks[method] = rank
            cur.scores.update(h.scores)
    for h in fused.values():
        h.score = sum(1.0 / (RRF_K + r) for r in h.ranks.values())
    return sorted(fused.values(), key=lambda h: (-h.score, min(h.ranks.values())))[:k]


@dataclass
class SearchResult:
    method: Method
    hits: list[Hit]
    timings_ms: dict[str, float]


def search(
    db: Session,
    embedder: Embedder,
    query: str,
    *,
    method: Method = "hybrid",
    k: int = 8,
    filters: Filters | None = None,
    min_score: float | None = None,
) -> SearchResult:
    filters = filters or Filters()
    timings: dict[str, float] = {}
    lists: dict[str, list[Hit]] = {}
    pool = k * 4 if method == "hybrid" else k
    if method in {"vector", "hybrid"}:
        t = time.perf_counter()
        lists["vector"] = vector_search(db, embedder, query, pool, filters)
        timings["vector"] = (time.perf_counter() - t) * 1000
    if method in {"keyword", "hybrid"}:
        t = time.perf_counter()
        lists["keyword"] = keyword_search(db, query, pool, filters)
        timings["keyword"] = (time.perf_counter() - t) * 1000
    if method == "hybrid":
        hits = rrf(lists, k)
    else:
        hits = lists[method][:k]
        for i, h in enumerate(hits, start=1):
            h.ranks[method] = i
    if min_score is not None:
        hits = [h for h in hits if h.score >= min_score]
    return SearchResult(method, hits, {k_: round(v, 2) for k_, v in timings.items()})


def expand(db: Session, hit: Hit, window: int = 1) -> list[Passage]:
    """Neighbouring passages of the same version (for context windows / reading)."""
    return list(
        db.scalars(
            select(Passage)
            .where(
                Passage.version_id == hit.version_id,
                Passage.ordinal.between(hit.ordinal - window, hit.ordinal + window),
            )
            .order_by(Passage.ordinal)
        )
    )
