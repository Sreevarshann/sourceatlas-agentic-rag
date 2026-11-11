from __future__ import annotations

import io
import time
from pathlib import Path

from fastapi.testclient import TestClient

from tests.fixtures.make_files import make_pdf

MD = b"# Refund Policy\nCustomers may request a refund within 14 days.\n## Exceptions\nGift cards are non-refundable.\n"


def up(client: TestClient, name: str, data: bytes, **form: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/documents", files={"file": (name, data)}, data={"collection": "Policies", **form}
    )


def test_upload_markdown_processes_into_passages(client: TestClient) -> None:
    res = up(client, "refunds.md", MD, tags="policy, refunds", meta='{"effective_date": "2025-01-01"}')
    assert res.status_code == 202, res.text
    d = res.json()
    assert d["status"] == "ready" and d["title"] == "Refund Policy" and d["tags"] == ["policy", "refunds"]
    assert d["meta"]["effective_date"] == "2025-01-01"
    assert d["current"]["embedding_model"] == "hashing-v1" and d["current"]["passage_count"] == 2
    ps = client.get(f"/api/documents/{d['id']}/passages").json()
    assert ps[1]["section"] == "Refund Policy > Exceptions" and "Gift cards" in ps[1]["text"]
    detail = client.get(f"/api/passages/{ps[0]['id']}", params={"context": 1}).json()
    assert detail["document"]["title"] == "Refund Policy" and len(detail["context"]) == 2


def test_pdf_passages_carry_page_numbers(client: TestClient, tmp_path: Path) -> None:
    pdf = make_pdf(
        tmp_path / "manual.pdf",
        ["Install the gateway on a flat surface.", "Reset by holding the button for ten seconds."],
        title="Gateway Manual",
    )
    d = up(client, "manual.pdf", pdf.read_bytes()).json()
    pages = [p["page"] for p in client.get(f"/api/documents/{d['id']}/passages").json()]
    assert pages == [1, 2] and d["current"]["page_count"] == 2
    f = client.get(f"/api/documents/{d['id']}/file")
    assert f.headers["content-type"] == "application/pdf" and f.content.startswith(b"%PDF")


def test_duplicate_upload_rejected_and_new_version_supported(client: TestClient) -> None:
    d = up(client, "refunds.md", MD).json()
    dup = up(client, "copy.md", MD)
    assert dup.status_code == 422 and "identical" in dup.json()["detail"]
    v2 = client.post(
        f"/api/documents/{d['id']}/versions",
        files={"file": ("refunds.md", MD + b"Refunds over $500 need approval.\n")},
    ).json()
    assert [v["version"] for v in v2["versions"]] == [1, 2] and v2["current"]["version"] == 2


def test_uploaded_html_is_never_served_as_html(client: TestClient) -> None:
    d = up(
        client, "x.html", b"<html><body><h1>Hi</h1><p>Text here.</p><script>alert(1)</script></body></html>"
    ).json()
    f = client.get(f"/api/documents/{d['id']}/file")
    assert f.headers["content-type"].startswith("text/plain")
    assert (
        f.headers["x-content-type-options"] == "nosniff" and "sandbox" in f.headers["content-security-policy"]
    )


def test_failed_parse_is_recorded_without_content(client: TestClient) -> None:
    d = up(client, "broken.pdf", b"%PDF-1.4 TOP-SECRET-BYTES").json()
    assert d["status"] == "failed" and "TOP-SECRET" not in (d["current"]["error"] or "")


def test_invalid_uploads_rejected(client: TestClient) -> None:
    assert up(client, "x.exe", b"MZ").status_code == 422
    assert up(client, "x.md", b"").status_code == 422
    assert up(client, "x.md", MD, meta="not json").status_code == 422


def test_reindex_delete_and_filters(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    d = up(client, "refunds.md", MD, tags="policy").json()
    assert client.post(f"/api/documents/{d['id']}/reindex").json()["status"] == "ready"
    assert [x["id"] for x in client.get("/api/documents", params={"tag": "policy"}).json()] == [d["id"]]
    assert client.get("/api/documents", params={"q": "refund"}).json()[0]["id"] == d["id"]
    assert client.get("/api/collections").json()[0] == {
        "id": d["collection_id"],
        "name": "Policies",
        "description": None,
        "document_count": 1,
    }
    assert client.delete(f"/api/documents/{d['id']}").status_code == 204
    assert not (settings.storage_dir / d["id"]).exists()
    assert client.get(f"/api/documents/{d['id']}").status_code == 404


def test_background_processing_reports_state(settings) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from sourceatlas.main import create_app

    app = create_app(settings.model_copy(update={"ingest_inline": False}))
    with TestClient(app) as c:
        with app.state.engine.begin() as conn:
            conn.execute(text("TRUNCATE collections CASCADE"))
        d = c.post("/api/documents", files={"file": ("a.md", io.BytesIO(MD))}).json()
        assert d["status"] in {"pending", "processing", "ready"}
        for _ in range(50):
            if c.get(f"/api/documents/{d['id']}").json()["status"] == "ready":
                break
            time.sleep(0.1)
        assert c.get(f"/api/documents/{d['id']}").json()["status"] == "ready"
