from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from sourceatlas.ingest.extract import ExtractionError, detect_kind, extract, safe_filename
from tests.fixtures.make_files import make_docx, make_pdf


def test_pdf_keeps_page_provenance(tmp_path: Path) -> None:
    p = make_pdf(
        tmp_path / "policy.pdf",
        ["Refunds are issued within 14 days.", "Exchanges require a receipt."],
        title="Refund Policy",
    )
    out = extract(p, detect_kind(p.name, p.read_bytes()[:16]))
    assert out.page_count == 2 and out.title == "Refund Policy"
    assert [s.page for s in out.segments] == [1, 2]
    assert "14 days" in out.segments[0].text and out.segments[1].section == "Page 2 heading"


def test_docx_sections_follow_heading_hierarchy(tmp_path: Path) -> None:
    p = make_docx(
        tmp_path / "guide.docx",
        [
            ("h1", "Engineering Guide"),
            ("p", "Intro text."),
            ("h2", "Code Review"),
            ("p", "Two approvals are required."),
        ],
    )
    out = extract(p, "docx")
    assert out.segments[-1].section == "Engineering Guide > Code Review"
    assert "Two approvals" in out.segments[-1].text


def test_markdown_sections(tmp_path: Path) -> None:
    p = tmp_path / "notes.md"
    p.write_text("# Handbook\nWelcome.\n## Leave\nEmployees get 20 days.\n### Carry-over\nUp to 5 days.\n")
    out = extract(p, "markdown")
    assert [s.section for s in out.segments] == [
        "Handbook",
        "Handbook > Leave",
        "Handbook > Leave > Carry-over",
    ]
    assert out.title == "Handbook"


def test_html_drops_scripts_and_keeps_headings(tmp_path: Path) -> None:
    p = tmp_path / "page.html"
    p.write_text(
        "<html><head><title>Status</title><script>alert('x')</script></head><body><nav>menu</nav><main><h1>Uptime</h1><p>99.9% SLA.</p></main></body></html>"
    )
    out = extract(p, "html")
    text = " ".join(s.text for s in out.segments)
    assert "99.9% SLA" in text and "alert" not in text and "menu" not in text
    assert out.segments[0].section == "Uptime"


@pytest.mark.parametrize(
    ("name", "head", "msg"),
    [
        ("x.exe", b"MZ", "Unsupported"),
        ("x.pdf", b"hello", "PDF"),
        ("x.docx", b"%PDF-", "DOCX"),
        ("x.txt", b"a\x00b", "binary"),
    ],
)
def test_detect_kind_rejects(name: str, head: bytes, msg: str) -> None:
    with pytest.raises(ExtractionError, match=msg):
        detect_kind(name, head)


def test_corrupt_pdf_error_has_no_content(tmp_path: Path) -> None:
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-1.7 SECRET-CONTENT garbage")
    with pytest.raises(ExtractionError) as info:
        extract(p, "pdf")
    assert "SECRET" not in str(info.value)


def test_docx_zip_bomb_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sourceatlas.ingest import extract as mod

    p = make_docx(tmp_path / "big.docx", [("p", "x" * 5000)])
    monkeypatch.setattr(mod, "MAX_DOCX_UNCOMPRESSED", 100)
    with pytest.raises(ExtractionError, match="unsafe size"):
        extract(p, "docx")


def test_non_docx_zip_rejected(tmp_path: Path) -> None:
    p = tmp_path / "fake.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(ExtractionError, match="does not match"):
        extract(p, "docx")


def test_empty_text_rejected(tmp_path: Path) -> None:
    p = tmp_path / "e.txt"
    p.write_text("   \n  ")
    with pytest.raises(ExtractionError, match="No extractable text"):
        extract(p, "text")


def test_safe_filename() -> None:
    assert safe_filename("../../etc/passwd.txt") == "passwd.txt"
    with pytest.raises(ExtractionError):
        safe_filename("..")
