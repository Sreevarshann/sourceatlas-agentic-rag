from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text


def test_health_reports_database_and_pgvector(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["pgvector"] is not None
    assert body["embedding_provider"] == "hashing"


def test_schema_has_hybrid_indexes(client: TestClient) -> None:
    engine = client.app.state.engine  # type: ignore[attr-defined]
    names = {i["name"] for i in inspect(engine).get_indexes("passages")}
    assert {"ix_passages_tsv", "ix_passages_embedding"} <= names
    with engine.connect() as c:
        method = c.execute(
            text(
                "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid = c.relam WHERE c.relname = 'ix_passages_embedding'"
            )
        ).scalar()
    assert method == "hnsw"


def test_tsvector_is_generated(client: TestClient) -> None:
    engine = client.app.state.engine  # type: ignore[attr-defined]
    with engine.begin() as c:
        c.execute(text("INSERT INTO collections (id, name, created_at) VALUES ('c1', 'x', now())"))
        c.execute(
            text(
                "INSERT INTO documents (id, collection_id, title, source_type, tags, meta, created_at) VALUES ('d1', 'c1', 't', 'upload', '[]', '{}', now())"
            )
        )
        c.execute(
            text(
                "INSERT INTO document_versions (id, document_id, version, filename, mime, sha256, size_bytes, status, passage_count, created_at) VALUES ('v1', 'd1', 1, 'a.txt', 'text/plain', 'x', 1, 'ready', 0, now())"
            )
        )
        c.execute(
            text(
                "INSERT INTO passages (id, version_id, document_id, collection_id, ordinal, text, char_start, char_end, token_count) VALUES ('p1', 'v1', 'd1', 'c1', 0, 'Refunds are processed within fourteen days', 0, 10, 6)"
            )
        )
        hit = c.execute(
            text("SELECT id FROM passages WHERE tsv @@ plainto_tsquery('english', 'refund processing')")
        ).scalar()
    assert hit == "p1"
