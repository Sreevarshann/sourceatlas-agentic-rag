from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from sourceatlas.agent.graph import build_graph
from sourceatlas.db.models import ResearchSession
from sourceatlas.embed.providers import Embedder
from sourceatlas.llm.base import LLMProvider

Sink = Callable[[dict[str, Any]], None]


def run_research(
    db: Session,
    embedder: Embedder,
    llm: LLMProvider,
    question: str,
    *,
    filters: dict[str, Any] | None = None,
    parent_id: str | None = None,
    on_event: Sink | None = None,
) -> ResearchSession:
    t0 = time.perf_counter()
    emit = on_event or (lambda _e: None)
    rs = ResearchSession(
        question=question,
        filters=filters or {},
        parent_id=parent_id,
        model_name=f"{llm.name}:{llm.model}",
        embedder=embedder.name,
    )
    db.add(rs)
    db.commit()
    emit({"type": "session", "id": rs.id, "status": "running"})
    state: dict[str, Any] = {}
    try:
        for mode, chunk in build_graph(db, embedder, llm).stream(
            {"question": question, "filters": filters or {}}, stream_mode=["custom", "values"]
        ):
            if mode == "custom":
                emit(chunk)
            else:
                state = chunk
    except Exception:
        rs.status = "failed"
        rs.duration_ms = int((time.perf_counter() - t0) * 1000)
        db.commit()
        raise
    answer = state.get("answer") or {}
    rs.answer = answer
    rs.status = answer.get("status", "failed")
    rs.evidence = state.get("evidence", [])
    rs.quarantined = state.get("quarantined", [])
    rs.trace = state.get("trace", [])
    rs.llm_usage = {
        "calls": llm.usage.calls,
        "prompt_tokens": llm.usage.prompt_tokens,
        "completion_tokens": llm.usage.completion_tokens,
        "latency_ms": round(llm.usage.latency_ms, 1),
    }
    rs.duration_ms = int((time.perf_counter() - t0) * 1000)
    db.commit()
    return rs


def evidence_graph(rs: ResearchSession) -> dict[str, Any]:
    """Nodes/edges derived only from recorded relationships: question → claim (answers),
    claim → passage (supports / unsupported), passage → document (in), passage ↔ passage
    (conflicts), question → passage (retrieved)."""
    nodes: list[dict[str, Any]] = [{"id": "q", "type": "question", "label": rs.question}]
    edges: list[dict[str, Any]] = []
    docs: dict[str, dict[str, Any]] = {}
    for p in rs.evidence:
        pid = f"p:{p['passage_id']}"
        nodes.append(
            {
                "id": pid,
                "type": "passage",
                "label": p["ref"],
                "text": p["text"][:300],
                "document_id": p["document_id"],
                "page": p.get("page"),
                "section": p.get("section"),
                "score": p.get("score"),
            }
        )
        edges.append({"id": f"q-{pid}", "source": "q", "target": pid, "kind": "retrieved", "rank": p["ref"]})
        docs.setdefault(
            p["document_id"],
            {
                "id": f"d:{p['document_id']}",
                "type": "document",
                "label": p["document_title"],
                "version": p.get("version"),
                "meta": p.get("meta", {}),
            },
        )
        edges.append(
            {"id": f"{pid}-d", "source": pid, "target": f"d:{p['document_id']}", "kind": "in_document"}
        )
    nodes += list(docs.values())
    for i, c in enumerate((rs.answer or {}).get("claims", [])):
        cid = f"c:{i}"
        nodes.append({"id": cid, "type": "claim", "label": c["text"][:160], "supported": c["supported"]})
        edges.append({"id": f"q-{cid}", "source": "q", "target": cid, "kind": "answers"})
        for cit in c["citations"]:
            edges.append(
                {
                    "id": f"{cid}-{cit['passage_id']}",
                    "source": cid,
                    "target": f"p:{cit['passage_id']}",
                    "kind": "supports" if c["supported"] else "unsupported",
                }
            )
    for j, cf in enumerate((rs.answer or {}).get("conflicts", [])):
        edges.append(
            {
                "id": f"x{j}",
                "source": f"p:{cf['a_passage']}",
                "target": f"p:{cf['b_passage']}",
                "kind": "conflicts",
                "detail": cf["detail"],
            }
        )
    return {"nodes": nodes, "edges": edges}
