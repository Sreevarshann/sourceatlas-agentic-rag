"""LIVE: real Ollama LLM (qwen3:4b-instruct) + nomic-embed-text. Excluded from CI."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from sourceatlas.config import Settings
from sourceatlas.main import create_app
from tests.test_research import INJECT, SEC, V1, V2

pytestmark = pytest.mark.live


@pytest.fixture
def live(tmp_path: Path, database_url: str) -> Iterator[TestClient]:
    try:
        names = {m["name"] for m in httpx.get("http://127.0.0.1:11434/api/tags", timeout=2).json()["models"]}
    except httpx.HTTPError:
        pytest.skip("Ollama not running")
    if not {"qwen3:4b-instruct", "nomic-embed-text:latest"} <= names:
        pytest.skip("required models not pulled")
    s = Settings(
        environment="test",
        database_url=database_url,
        data_dir=tmp_path / "v",
        ingest_inline=True,
        embedding_provider="ollama",
        llm_provider="ollama",
        log_level="WARNING",
    )
    app = create_app(s)
    with TestClient(app) as c:
        with app.state.engine.begin() as conn:
            conn.execute(text("TRUNCATE collections, research_sessions CASCADE"))
        for name, data, meta in [
            ("refunds-2024.md", V1, {"policy": "refunds", "effective_date": "2024-01-01"}),
            ("refunds-2025.md", V2, {"policy": "refunds", "effective_date": "2025-03-01"}),
            ("shipping.md", INJECT, {}),
            ("security.md", SEC, {}),
        ]:
            assert (
                c.post(
                    "/api/documents",
                    files={"file": (name, data)},
                    data={"collection": "Policies", "meta": json.dumps(meta)},
                ).json()["status"]
                == "ready"
            )
        yield c


@pytest.mark.parametrize(
    ("question", "must_contain"),
    [
        ("How often must services rotate credentials?", "90"),
        ("What is the current refund window?", "30"),
        ("How long does shipping take?", "3"),
    ],
)
def test_live_research(live: TestClient, question: str, must_contain: str) -> None:
    rs = live.post("/api/research", json={"question": question}).json()
    a = rs["answer"]
    supported = [c for c in a["claims"] if c["supported"]]
    print(
        f"\n{question} -> {a['status']} {rs['duration_ms']}ms conflicts={len(a['conflicts'])} quarantined={len(rs['quarantined'])}"
    )
    for c in a["claims"]:
        print(
            "  ",
            "OK " if c["supported"] else "REJ",
            c["text"][:110],
            [x["ref"] for x in c["citations"]],
            c["support"]["reason"],
        )
    assert supported and any(must_contain in c["text"] for c in supported)
    assert all("90 days" not in c["text"] for c in supported if "refund" in c["text"].lower())
