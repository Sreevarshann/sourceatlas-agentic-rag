"""Agentic research graph (LangGraph).

  understand ─▶ retrieve ─▶ assess ──(insufficient & budget)──▶ reformulate ─▶ retrieve
                                 │
                                 ▼
                     rerank ─▶ conflicts ─▶ draft ─▶ verify ─▶ END

Bounded: at most MAX_ROUNDS retrieval rounds and MAX_QUERIES queries per round.
Tool calls and decisions are recorded in ``trace``; no hidden model reasoning is stored.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from sourceatlas.agent import prompts
from sourceatlas.agent.evidence import (
    claim_support,
    conflict_candidates,
    coverage,
    looks_like_injection,
    rerank,
    strip_injection,
)
from sourceatlas.db.models import Collection, Passage
from sourceatlas.embed.providers import Embedder
from sourceatlas.llm.base import LLMError, LLMProvider
from sourceatlas.retrieval.search import Filters, search

MAX_ROUNDS = 3
MAX_QUERIES = 3
EVIDENCE_K = 6
MAX_CONFLICT_JUDGEMENTS = 2
SUFFICIENT_COVERAGE = 0.6

UNDERSTAND_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["factual", "comparison", "summary", "out_of_scope"]},
        "queries": {"type": "array", "items": {"type": "string"}},
        "collections": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "queries"],
}
QUERIES_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
}
DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "abstain": {"type": "boolean"},
        "reason": {"type": ["string", "null"]},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "citations"],
            },
        },
        "follow_ups": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["abstain", "claims"],
}
CONFLICT_SCHEMA = {
    "type": "object",
    "properties": {"conflict": {"type": "boolean"}, "explanation": {"type": "string"}},
    "required": ["conflict", "explanation"],
}


class ResearchState(TypedDict, total=False):
    question: str
    filters: dict[str, Any]
    intent: str
    queries: list[str]
    round: int
    hits: dict[str, dict[str, Any]]
    quarantined: list[dict[str, Any]]
    sufficient: bool
    evidence: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    draft: dict[str, Any]
    answer: dict[str, Any]
    trace: list[dict[str, Any]]


def _emit(e: dict[str, Any]) -> None:
    with contextlib.suppress(RuntimeError):
        get_stream_writer()(e)


def _t(state: ResearchState, node: str, t0: float, **d: Any) -> list[dict[str, Any]]:
    entry = {"node": node, "ms": round((time.perf_counter() - t0) * 1000, 1), **d}
    _emit({"type": "stage", "stage": node, "status": "done", **entry})
    return [*state.get("trace", []), entry]


def _add(graph: Any, name: str, fn: Callable[[ResearchState], ResearchState]) -> None:
    """LangGraph's ``add_node`` overloads do not type-check under mypy --strict in this
    release (even for a minimal TypedDict example), so registration goes through here."""
    graph.add_node(name, fn)


def build_graph(db: Session, embedder: Embedder, llm: LLMProvider) -> Any:
    def understand(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "understand", "status": "start"})
        names = [c for c in db.scalars(select(Collection.name))]
        try:
            out = llm.complete_json(
                task="understand",
                system=prompts.UNDERSTAND_SYSTEM,
                user=f"Collections: {names}\nQuestion: {s['question']}",
                schema=UNDERSTAND_SCHEMA,
                payload={"question": s["question"]},
            )
        except LLMError:
            out = {"intent": "factual", "queries": [s["question"]]}
        queries = [
            q.strip()[:300]
            for q in [s["question"], *out.get("queries", [])]
            if isinstance(q, str) and q.strip()
        ]
        queries = list(dict.fromkeys(queries))[:MAX_QUERIES]
        filters = dict(s.get("filters") or {})
        cols = [c for c in out.get("collections") or [] if c in names]
        if cols and not filters.get("collections") and not filters.get("collection_ids"):
            filters["collections"] = cols
        return {
            "intent": str(out.get("intent", "factual")),
            "queries": queries,
            "filters": filters,
            "round": 0,
            "hits": {},
            "quarantined": [],
            "trace": _t(s, "understand", t0, intent=out.get("intent"), queries=queries, collections=cols),
        }

    def retrieve(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "retrieve", "status": "start", "round": s["round"] + 1})
        hits = dict(s.get("hits", {}))
        quarantined = list(s.get("quarantined", []))
        calls = []
        for q in s["queries"]:
            res = search(
                db, embedder, q, method="hybrid", k=EVIDENCE_K, filters=Filters(**s.get("filters", {}))
            )
            calls.append(
                {"tool": "hybrid_search", "query": q, "hits": len(res.hits), "timings_ms": res.timings_ms}
            )
            for h in res.hits:
                d = asdict(h)
                if looks_like_injection(d["text"]):
                    clean, removed = strip_injection(d["text"])
                    if d["passage_id"] not in {x["passage_id"] for x in quarantined}:
                        quarantined.append(
                            {
                                **d,
                                "removed_sentences": removed,
                                "reason": "instruction-like sentences removed (possible prompt injection)",
                            }
                        )
                    if not clean:
                        continue
                    d = {**d, "text": clean, "sanitized": True}
                if d["passage_id"] not in hits or d["score"] > hits[d["passage_id"]]["score"]:
                    hits[d["passage_id"]] = {**d, "query": q}
        _emit({"type": "retrieval", "round": s["round"] + 1, "calls": calls, "quarantined": len(quarantined)})
        return {
            "hits": hits,
            "quarantined": quarantined,
            "round": s["round"] + 1,
            "trace": _t(s, "retrieve", t0, round=s["round"] + 1, calls=calls),
        }

    def assess(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        top = sorted(s["hits"].values(), key=lambda h: -h["score"])[:EVIDENCE_K]
        cov = coverage(s["question"], [h["text"] for h in top] + [h.get("section") or "" for h in top])
        ok = bool(top) and cov >= SUFFICIENT_COVERAGE
        return {
            "sufficient": ok,
            "trace": _t(s, "assess", t0, coverage=round(cov, 3), passages=len(top), sufficient=ok),
        }

    def reformulate(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        try:
            out = llm.complete_json(
                task="reformulate",
                system=prompts.REFORMULATE_SYSTEM,
                user=f"Question: {s['question']}\nTried: {s['queries']}",
                schema=QUERIES_SCHEMA,
                payload={"question": s["question"], "tried": s["queries"]},
            )
            qs = [
                q.strip()[:300]
                for q in out.get("queries", [])
                if isinstance(q, str) and q.strip() and q not in s["queries"]
            ][:MAX_QUERIES]
        except LLMError:
            qs = []
        return {"queries": qs or s["queries"], "trace": _t(s, "reformulate", t0, queries=qs)}

    def do_rerank(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        ranked = rerank(s["question"], list(s["hits"].values()))[:EVIDENCE_K]
        for i, h in enumerate(ranked, start=1):
            h["ref"] = f"P{i}"
        _emit({"type": "evidence", "evidence": ranked, "quarantined": s.get("quarantined", [])})
        return {
            "evidence": ranked,
            "trace": _t(s, "rerank", t0, kept=len(ranked), method="heuristic: rrf + term coverage"),
        }

    def conflicts(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        ids = [h["passage_id"] for h in s["evidence"]]
        vecs = {
            p.id: (list(p.embedding) if p.embedding is not None else None)
            for p in db.scalars(select(Passage).where(Passage.id.in_(ids)))
        }
        out = []
        for c in conflict_candidates(s["evidence"], vecs)[:MAX_CONFLICT_JUDGEMENTS]:
            judged: dict[str, Any] = {"conflict": True, "explanation": c.detail}
            with contextlib.suppress(LLMError):
                judged = llm.complete_json(
                    task="conflict",
                    system=prompts.CONFLICT_SYSTEM,
                    user=f"A ({c.a['document_title']}): {c.a['text']}\n\nB ({c.b['document_title']}): {c.b['text']}",
                    schema=CONFLICT_SCHEMA,
                    payload={"a": c.a["text"], "b": c.b["text"]},
                )
            if judged.get("conflict"):
                out.append(
                    {
                        "a": c.a["ref"],
                        "b": c.b["ref"],
                        "a_passage": c.a["passage_id"],
                        "b_passage": c.b["passage_id"],
                        "kind": c.kind,
                        "detail": c.detail,
                        "explanation": str(judged.get("explanation", ""))[:500],
                        "newer": next((h["ref"] for h in s["evidence"] if h["passage_id"] == c.newer), None),
                        "signals": c.signals,
                    }
                )
        if out:
            _emit({"type": "conflicts", "conflicts": out})
        return {"conflicts": out, "trace": _t(s, "conflicts", t0, found=len(out))}

    def draft(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "draft", "status": "start"})
        ev = s["evidence"]
        d: dict[str, Any]
        if s.get("intent") == "out_of_scope" and not s.get("sufficient"):
            d = {
                "abstain": True,
                "reason": "This question is outside the scope of the document library.",
                "claims": [],
                "follow_ups": [],
            }
        elif not ev:
            d = {
                "abstain": True,
                "reason": "No relevant passages were found in the library.",
                "claims": [],
                "follow_ups": [],
            }
        else:
            evidence = "\n\n".join(
                f"[{h['ref']}] {h['document_title']} (v{h['version']}{', p.' + str(h['page']) if h['page'] else ''}{', ' + h['section'] if h['section'] else ''}{', effective ' + str(h['meta'].get('effective_date')) if h['meta'].get('effective_date') else ''}):\n{h['text']}"
                for h in ev
            )
            conf = "".join(
                f"Known conflict: {c['a']} vs {c['b']} — {c['detail']}"
                + (f" ({c['newer']} is newer)" if c["newer"] else "")
                + "\n"
                for c in s.get("conflicts", [])
            )
            try:
                d = llm.complete_json(
                    task="draft",
                    system=prompts.DRAFT_SYSTEM,
                    user=prompts.DRAFT_USER.format(
                        question=s["question"], evidence=evidence, conflicts=conf + "\n" if conf else ""
                    ),
                    schema=DRAFT_SCHEMA,
                    payload={"question": s["question"], "evidence": ev, "conflicts": s.get("conflicts", [])},
                )
            except LLMError as exc:
                d = {
                    "abstain": True,
                    "reason": f"The answer could not be drafted ({exc}).",
                    "claims": [],
                    "follow_ups": [],
                }
        return {
            "draft": d,
            "trace": _t(s, "draft", t0, claims=len(d.get("claims", [])), abstain=bool(d.get("abstain"))),
        }

    def verify(s: ResearchState) -> ResearchState:
        t0 = time.perf_counter()
        by_ref = {h["ref"]: h for h in s["evidence"]}
        ids = [h["passage_id"] for h in s["evidence"]]
        vecs = {
            p.id: (list(p.embedding) if p.embedding is not None else None)
            for p in db.scalars(select(Passage).where(Passage.id.in_(ids)))
        }
        d = s["draft"]
        claims = []
        for c in d.get("claims", [])[:12]:
            text = str(c.get("text", "")).strip()[:1000]
            refs = [r for r in c.get("citations", []) if isinstance(r, str)]
            valid = [r for r in refs if r in by_ref]
            invalid = [r for r in refs if r not in by_ref]
            cvec = embedder.embed_query(text) if text and valid else None
            headers = [
                f"{by_ref[r]['document_title']} v{by_ref[r]['version']} {by_ref[r].get('section') or ''} {by_ref[r]['meta'].get('effective_date') or ''}"
                for r in valid
            ]
            sup = claim_support(
                text,
                [by_ref[r]["text"] for r in valid],
                cvec,
                [vecs.get(by_ref[r]["passage_id"]) for r in valid],
                question=s["question"],
                headers=headers,
            )
            claims.append(
                {
                    "text": text,
                    "citations": [
                        {
                            "ref": r,
                            "passage_id": by_ref[r]["passage_id"],
                            "document_id": by_ref[r]["document_id"],
                            "document_title": by_ref[r]["document_title"],
                            "version": by_ref[r]["version"],
                            "page": by_ref[r]["page"],
                            "section": by_ref[r]["section"],
                            "excerpt": by_ref[r]["text"][:400],
                            "source_uri": by_ref[r].get("source_uri"),
                        }
                        for r in valid
                    ],
                    "invalid_citations": invalid,
                    "supported": sup.supported,
                    "support": asdict(sup),
                }
            )
        supported = [c for c in claims if c["supported"]]
        abstain = bool(d.get("abstain")) or not supported
        reason = (
            d.get("reason")
            if d.get("abstain")
            else (
                None
                if supported
                else "None of the drafted claims could be verified against the cited passages."
            )
        )
        status = (
            "abstained"
            if abstain
            else ("verified" if len(supported) == len(claims) else "partially_verified")
        )
        answer = {
            "status": status,
            "abstain": abstain,
            "reason": reason,
            "claims": claims,
            "conflicts": s.get("conflicts", []),
            "follow_ups": [str(x)[:200] for x in d.get("follow_ups", [])][:3],
            "intent": s.get("intent"),
        }
        _emit({"type": "answer", "answer": answer})
        return {
            "answer": answer,
            "trace": _t(s, "verify", t0, claims=len(claims), supported=len(supported), status=status),
        }

    def route(s: ResearchState) -> str:
        return (
            "reformulate"
            if not s["sufficient"] and s["round"] < MAX_ROUNDS and s.get("intent") != "out_of_scope"
            else "rerank"
        )

    g = StateGraph(ResearchState)
    _add(g, "understand", understand)
    _add(g, "retrieve", retrieve)
    _add(g, "assess", assess)
    _add(g, "reformulate", reformulate)
    _add(g, "rerank", do_rerank)
    _add(g, "conflicts", conflicts)
    _add(g, "draft", draft)
    _add(g, "verify", verify)
    g.add_edge(START, "understand")
    g.add_edge("understand", "retrieve")
    g.add_edge("retrieve", "assess")
    g.add_conditional_edges("assess", route, {"reformulate": "reformulate", "rerank": "rerank"})
    g.add_edge("reformulate", "retrieve")
    g.add_edge("rerank", "conflicts")
    g.add_edge("conflicts", "draft")
    g.add_edge("draft", "verify")
    g.add_edge("verify", END)
    return g.compile()
