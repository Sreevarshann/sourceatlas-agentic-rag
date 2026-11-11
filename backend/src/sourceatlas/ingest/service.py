"""Document lifecycle: upload → validate → store → (background) extract → chunk → embed →
index; plus versioning, deduplication, reindexing and deletion."""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from sourceatlas.config import Settings
from sourceatlas.db.models import Collection, Document, DocumentVersion, Passage
from sourceatlas.embed.providers import Embedder, EmbeddingError
from sourceatlas.ingest.chunk import chunk_segments
from sourceatlas.ingest.extract import MIME, ExtractionError, detect_kind, extract, safe_filename

log = logging.getLogger("sourceatlas.ingest")


class IngestError(ValueError):
    pass


def spool(src: BinaryIO, settings: Settings) -> tuple[Path, str, int, bytes]:
    tmp = settings.data_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=tmp)
    path, digest, size, head = Path(name), hashlib.sha256(), 0, b""
    try:
        with open(fd, "wb") as fh:
            while chunk := src.read(1 << 20):
                if not head:
                    head = chunk[:16]
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise IngestError(f"File exceeds the {settings.max_upload_bytes // (1 << 20)} MB limit")
                digest.update(chunk)
                fh.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise IngestError("File is empty")
    return path, digest.hexdigest(), size, head


def get_or_create_collection(db: Session, name: str) -> Collection:
    c = db.scalars(select(Collection).where(Collection.name == name)).first()
    if c is None:
        c = Collection(name=name)
        db.add(c)
        db.flush()
    return c


def register_upload(
    db: Session,
    settings: Settings,
    *,
    collection: Collection,
    src: BinaryIO,
    filename: str | None,
    title: str | None = None,
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    document: Document | None = None,
) -> DocumentVersion:
    """Validate and store a file, creating a document (or a new version of ``document``).
    Processing happens later via :func:`process_version`."""
    name = safe_filename(filename)
    path, sha, size, head = spool(src, settings)
    try:
        kind = detect_kind(name, head)
        dup = db.scalars(
            select(DocumentVersion)
            .join(Document)
            .where(
                DocumentVersion.sha256 == sha,
                Document.collection_id == collection.id,
                DocumentVersion.status != "failed",
            )
        ).first()
        if dup is not None:
            raise IngestError(f"An identical file is already in this collection ({dup.filename})")
        if document is None:
            document = Document(
                collection_id=collection.id,
                title=title or Path(name).stem,
                source_type="upload",
                tags=tags or [],
                meta=meta or {},
            )
            db.add(document)
            db.flush()
        n = max((v.version for v in document.versions), default=0) + 1
        dest = settings.storage_dir / document.id / f"v{n}{Path(name).suffix.lower()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(path, dest)
        ver = DocumentVersion(
            document_id=document.id,
            version=n,
            filename=name,
            mime=MIME[kind],
            sha256=sha,
            size_bytes=size,
            storage_path=str(dest.relative_to(settings.storage_dir)),
        )
        document.versions.append(ver)
        db.commit()
        return ver
    except (ExtractionError, IngestError):
        db.rollback()
        raise
    finally:
        path.unlink(missing_ok=True)


def process_version(db: Session, settings: Settings, embedder: Embedder, version_id: str) -> DocumentVersion:
    ver = db.get(DocumentVersion, version_id)
    if ver is None:
        raise IngestError("Version not found")
    ver.status, ver.error = "processing", None
    db.commit()
    try:
        assert ver.storage_path
        path = settings.storage_dir / ver.storage_path
        kind = detect_kind(ver.filename, path.read_bytes()[:16])
        extracted = extract(path, kind)
        chunks = chunk_segments(extracted.segments, settings.chunk_tokens, settings.chunk_overlap)
        vectors = embedder.embed_documents([f"{c.section or ''}\n{c.text}".strip() for c in chunks])
        doc = ver.document
        db.execute(delete(Passage).where(Passage.version_id == ver.id))
        db.add_all(
            Passage(
                version_id=ver.id,
                document_id=doc.id,
                collection_id=doc.collection_id,
                ordinal=c.ordinal,
                page=c.page,
                section=c.section,
                text=c.text,
                char_start=c.char_start,
                char_end=c.char_end,
                token_count=c.token_count,
                embedding=v,
            )
            for c, v in zip(chunks, vectors, strict=True)
        )
        if extracted.title and doc.title == Path(ver.filename).stem:
            doc.title = extracted.title[:300]
        ver.page_count, ver.passage_count, ver.embedding_model = (
            extracted.page_count,
            len(chunks),
            embedder.name,
        )
        ver.status, ver.processed_at = "ready", datetime.now(UTC)
        db.commit()
    except (ExtractionError, EmbeddingError) as exc:
        db.rollback()
        ver.status, ver.error = "failed", str(exc)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("processing_failed", extra={"version_id": version_id})
        ver.status, ver.error = "failed", "Unexpected processing error"
        db.commit()
    return ver


class Processor:
    """Small in-process background queue (state lives in the DB, so it is visible to the
    UI and survives as a 'failed'/'pending' record if the process dies)."""

    def __init__(
        self, factory: sessionmaker[Session], settings: Settings, embedder: Embedder, workers: int = 1
    ) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ingest")
        self._factory, self._settings, self._embedder = factory, settings, embedder

    def submit(self, version_id: str) -> None:
        self._pool.submit(self._run, version_id)

    def _run(self, version_id: str) -> None:
        with self._factory() as db:
            process_version(db, self._settings, self._embedder, version_id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)


def delete_document(db: Session, settings: Settings, doc: Document) -> None:
    target = (settings.storage_dir / doc.id).resolve()
    db.delete(doc)
    db.commit()
    if target.parent == settings.storage_dir.resolve() and target.is_dir():
        shutil.rmtree(target)
