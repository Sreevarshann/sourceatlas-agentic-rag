"""Content extraction with provenance (page for PDFs, heading path for structured text).

Untrusted files are never executed: PDF JavaScript/forms are ignored (text only), DOCX is
read via python-docx (zip size guarded), HTML scripts/styles are dropped. Errors are
reported without echoing file content.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePath

MAX_PDF_PAGES = 600
MAX_DOCX_UNCOMPRESSED = 200 * 1024 * 1024
MAX_TEXT_CHARS = 5_000_000

KINDS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
}
MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text": "text/plain",
    "markdown": "text/markdown",
    "html": "text/html",
}


class ExtractionError(ValueError):
    """User-facing, content-free extraction failure."""


@dataclass(frozen=True)
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


@dataclass
class Extracted:
    kind: str
    segments: list[Segment]
    page_count: int | None
    title: str | None


def safe_filename(name: str | None) -> str:
    base = PurePath((name or "").replace("\\", "/")).name.strip()
    if not base or base in {".", ".."}:
        raise ExtractionError("Missing filename")
    return base[:200]


def detect_kind(filename: str, head: bytes) -> str:
    kind = KINDS.get(PurePath(filename).suffix.lower())
    if kind is None:
        raise ExtractionError(f"Unsupported file type. Allowed: {', '.join(sorted(KINDS))}")
    if kind == "pdf" and not head.startswith(b"%PDF-"):
        raise ExtractionError("File content does not match PDF")
    if kind == "docx" and not head.startswith(b"PK\x03\x04"):
        raise ExtractionError("File content does not match DOCX")
    if kind in {"text", "markdown", "html"} and b"\x00" in head:
        raise ExtractionError("Text file appears to be binary")
    return kind


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line wraps
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract(path: Path, kind: str) -> Extracted:
    try:
        match kind:
            case "pdf":
                out = _pdf(path)
            case "docx":
                out = _docx(path)
            case "markdown" | "text":
                out = _markdown(_read_text(path), kind)
            case "html":
                out = _html(_read_text(path))
            case _:
                raise ExtractionError("Unsupported file type")
    except ExtractionError:
        raise
    except Exception as exc:  # parser failures -> generic message
        raise ExtractionError(f"Could not parse {kind} file ({type(exc).__name__})") from exc
    out.segments = [s for s in out.segments if s.text.strip()]
    if not out.segments:
        raise ExtractionError("No extractable text (scanned PDFs without OCR are not supported)")
    return out


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    if len(text) > MAX_TEXT_CHARS:
        raise ExtractionError("Text exceeds the size limit")
    return text


def _pdf(path: Path) -> Extracted:
    import pymupdf

    with pymupdf.open(path) as doc:  # type: ignore[no-untyped-call]  # PyMuPDF's open() is untyped
        if doc.needs_pass:
            raise ExtractionError("Encrypted PDFs are not supported")
        if doc.page_count > MAX_PDF_PAGES:
            raise ExtractionError(f"PDF has more than {MAX_PDF_PAGES} pages")
        title = (doc.metadata or {}).get("title") or None
        toc = {p: t for _lvl, t, p in doc.get_toc(simple=True)}
        segments, section = [], None
        for i, page in enumerate(doc, start=1):
            section = toc.get(i, section)
            segments.append(Segment(_clean(page.get_text("text")), page=i, section=section))
        return Extracted("pdf", segments, doc.page_count, title)


def _docx(path: Path) -> Extracted:
    import docx

    with zipfile.ZipFile(path) as zf:
        if sum(i.file_size for i in zf.infolist()) > MAX_DOCX_UNCOMPRESSED:
            raise ExtractionError("Document expands to an unsafe size")
        if "word/document.xml" not in zf.namelist():
            raise ExtractionError("File content does not match DOCX")
    d = docx.Document(str(path))
    segments: list[Segment] = []
    heading: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            segments.append(Segment(_clean("\n".join(buf)), section=" > ".join(heading) or None))
            buf.clear()

    for p in d.paragraphs:
        style = (p.style.name if p.style is not None else "") or ""
        if style.lower().startswith("heading") and p.text.strip():
            flush()
            level = int(re.sub(r"\D", "", style) or 1)
            heading[:] = [*heading[: level - 1], p.text.strip()]
        elif p.text.strip():
            buf.append(p.text)
    for table in d.tables:
        for row in table.rows:
            buf.append(" | ".join(c.text.strip() for c in row.cells))
    flush()
    title = d.core_properties.title or (
        segments[0].section.split(" > ")[0] if segments and segments[0].section else None
    )
    return Extracted("docx", segments, None, title)


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _markdown(text: str, kind: str) -> Extracted:
    segments: list[Segment] = []
    heading: list[str] = []
    buf: list[str] = []
    title = None

    def flush() -> None:
        if buf:
            segments.append(Segment(_clean("\n".join(buf)), section=" > ".join(heading) or None))
            buf.clear()

    for line in text.split("\n"):
        m = _MD_HEADING.match(line) if kind == "markdown" else None
        if m:
            flush()
            level = len(m.group(1))
            heading[:] = [*heading[: level - 1], m.group(2)]
            title = title or m.group(2)
        else:
            buf.append(line)
    flush()
    return Extracted(kind, segments, None, title)


def _html(text: str) -> Extracted:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(text, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "form", "template"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else None
    body = soup.find("main") or soup.find("article") or soup.body or soup
    segments: list[Segment] = []
    heading: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            segments.append(Segment(_clean("\n".join(buf)), section=" > ".join(heading) or None))
            buf.clear()

    for el in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "pre", "blockquote"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name in {"h1", "h2", "h3", "h4"}:
            flush()
            level = int(el.name[1])
            heading[:] = [*heading[: level - 1], txt]
            title = title or txt
        elif el.find_parent(["li", "td", "blockquote"]) is None or el.name in {"li", "td"}:
            buf.append(txt)
    flush()
    return Extracted("html", segments, None, title)
