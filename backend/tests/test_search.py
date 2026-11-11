from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from sourceatlas.retrieval.search import Hit, rrf

DOCS = {
    "refunds.md": (
        b"# Refund Policy\nCustomers may request a refund within 14 days of delivery.\n## Gift cards\nGift cards are non-refundable.\n",
        "policy",
        '{"policy": "refunds", "effective_date": "2024-01-01"}',
    ),
    "security.md": (
        b"# Security Guidelines\nAll services must rotate credentials every 90 days.\n## Passwords\nPasswords require 14 characters minimum.\n",
        "engineering",
        "{}",
    ),
    "gateway.md": (
        b"# Flux Gateway Manual\nHold the reset button for ten seconds to restore factory settings.\n",
        "manual",
        "{}",
    ),
}


@pytest.fixture
def corpus(client: TestClient) -> dict[str, Any]:
    out = {}
    for name, (data, tag, meta) in DOCS.items():
        out[name] = client.post(
            "/api/documents",
            files={"file": (name, data)},
            data={"collection": "Handbook" if tag != "manual" else "Manuals", "tags": tag, "meta": meta},
        ).json()
    return out


def s(client: TestClient, query: str, **kw: Any) -> list[dict[str, Any]]:
    res = client.post("/api/search", json={"query": query, **kw})
    assert res.status_code == 200, res.text
    return res.json()["hits"]


@pytest.mark.parametrize("method", ["vector", "keyword", "hybrid"])
def test_each_method_finds_the_relevant_passage(
    client: TestClient, corpus: dict[str, Any], method: str
) -> None:
    hits = s(client, "how do I reset the gateway to factory settings", method=method)
    assert hits and hits[0]["document_title"] == "Flux Gateway Manual"
    expected = {"vector", "keyword"} if method == "hybrid" else {method}
    assert set(hits[0]["ranks"]) == expected


def test_keyword_exact_term_match(client: TestClient, corpus: dict[str, Any]) -> None:
    hits = s(client, "credentials rotate", method="keyword")
    assert hits[0]["section"] == "Security Guidelines"


def test_hybrid_reports_both_ranks(client: TestClient, corpus: dict[str, Any]) -> None:
    hits = s(client, "gift cards refundable")
    top = hits[0]
    assert set(top["ranks"]) == {"vector", "keyword"} and "Gift cards" in top["text"]
    assert top["score"] == pytest.approx(sum(1 / (60 + r) for r in top["ranks"].values()))


def test_filters(client: TestClient, corpus: dict[str, Any]) -> None:
    assert {h["collection"] for h in s(client, "days", filters={"collections": ["Manuals"]})} <= {"Manuals"}
    assert all(
        h["document_id"] == corpus["security.md"]["id"]
        for h in s(client, "14", filters={"document_ids": [corpus["security.md"]["id"]]})
    )
    hits = s(client, "14 days", filters={"meta": {"policy": "refunds"}})
    assert hits and all(h["meta"]["policy"] == "refunds" for h in hits)
    assert all(
        h["document_title"] == "Flux Gateway Manual" for h in s(client, "reset", filters={"tags": ["manual"]})
    )


def test_only_current_version_is_searchable(client: TestClient, corpus: dict[str, Any]) -> None:
    doc = corpus["refunds.md"]
    client.post(
        f"/api/documents/{doc['id']}/versions",
        files={
            "file": (
                "refunds.md",
                b"# Refund Policy\nCustomers may request a refund within 30 days of delivery.\n",
            )
        },
    )
    texts = [h["text"] for h in s(client, "refund within days", method="keyword")]
    assert any("30 days" in t for t in texts) and not any("14 days of delivery" in t for t in texts)


def test_stopword_only_and_injection_queries_are_safe(client: TestClient, corpus: dict[str, Any]) -> None:
    assert s(client, "the of and", method="keyword") == []
    assert isinstance(s(client, "'; DROP TABLE passages; --", method="keyword"), list)
    assert client.get("/api/documents").status_code == 200


def test_min_score_threshold(client: TestClient, corpus: dict[str, Any]) -> None:
    assert s(client, "gateway reset", method="vector", min_score=0.999) == []


def _h(pid: str) -> Hit:
    return Hit(pid, "d", "v", "t", "c", 1, None, None, "x", 0, 0.0)


def test_rrf_math() -> None:
    fused = rrf({"vector": [_h("a"), _h("b")], "keyword": [_h("b"), _h("c")]}, k=3)
    assert [h.passage_id for h in fused] == ["b", "a", "c"]
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61)
