"""Builders for real test documents (PDF via reportlab, DOCX via python-docx)."""

from __future__ import annotations

import io
from pathlib import Path


def make_pdf(path: Path, pages: list[str], title: str = "Test PDF") -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle(title)
    for i, text in enumerate(pages, start=1):
        c.bookmarkPage(f"p{i}")
        c.addOutlineEntry(f"Page {i} heading", f"p{i}", level=0)
        y = 720
        for line in text.split("\n"):
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()
    return path


def make_docx(path: Path, blocks: list[tuple[str, str]], title: str = "Test DOCX") -> Path:
    import docx

    d = docx.Document()
    d.core_properties.title = title
    for kind, text in blocks:
        if kind.startswith("h"):
            d.add_heading(text, level=int(kind[1]))
        else:
            d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    path.write_bytes(buf.getvalue())
    return path
