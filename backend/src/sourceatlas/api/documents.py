from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from sourceatlas.api.deps import AppSettings, DbSession, DocumentDep
from sourceatlas.db.models import Collection, Document, DocumentVersion, Passage
from sourceatlas.ingest.extract import ExtractionError
from sourceatlas.ingest.service import (
    IngestError,
    delete_document,
    get_or_create_collection,
    process_version,
    register_upload,
)

router = APIRouter(tags=["library"])


class CollectionOut(BaseModel):
    id: str
    name: str
    description: str | None
    document_count: int


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class VersionOut(BaseModel):
    id: str
    version: int
    filename: str
    mime: str
    sha256: str
    size_bytes: int
    status: str
    error: str | None
    page_count: int | None
    passage_count: int
    embedding_model: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentOut(BaseModel):
    id: str
    collection_id: str
    collection: str
    title: str
    source_type: str
    source_uri: str | None
    tags: list[str]
    meta: dict[str, Any]
    created_at: datetime
    status: str
    current: VersionOut | None
    versions: list[VersionOut]


class PassageOut(BaseModel):
    id: str
    document_id: str
    version_id: str
    ordinal: int
    page: int | None
    section: str | None
    text: str
    char_start: int
    char_end: int
    token_count: int


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    tags: list[str] | None = Field(default=None, max_length=30)
    meta: dict[str, Any] | None = None


def doc_out(d: Document) -> DocumentOut:
    cur = d.current
    return DocumentOut(
        id=d.id, collection_id=d.collection_id, collection=d.collection.name, title=d.title, source_type=d.source_type,
        source_uri=d.source_uri, tags=list(d.tags), meta=dict(d.meta), created_at=d.created_at,
        status=cur.status if cur else "pending",
        current=VersionOut.model_validate(cur, from_attributes=True) if cur else None,
        versions=[VersionOut.model_validate(v, from_attributes=True) for v in d.versions],
    )  # fmt: skip


def _parse_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="meta must be a JSON object") from exc
    if not isinstance(meta, dict) or len(json.dumps(meta)) > 4000:
        raise HTTPException(status_code=422, detail="meta must be a JSON object under 4 KB")
    return meta


def _dispatch(request: Request, db: DbSession, ver: DocumentVersion) -> None:
    settings = request.app.state.settings
    if settings.ingest_inline:
        process_version(db, settings, request.app.state.embedder, ver.id)
    else:
        request.app.state.processor.submit(ver.id)


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(db: DbSession) -> list[CollectionOut]:
    rows = db.execute(
        select(Collection, func.count(Document.id))
        .outerjoin(Document)
        .group_by(Collection.id)
        .order_by(Collection.name)
    ).all()
    return [CollectionOut(id=c.id, name=c.name, description=c.description, document_count=n) for c, n in rows]


@router.post("/collections", response_model=CollectionOut, status_code=201)
def create_collection(body: CollectionIn, db: DbSession) -> CollectionOut:
    if db.scalars(select(Collection).where(Collection.name == body.name)).first():
        raise HTTPException(status_code=409, detail="Collection already exists")
    c = Collection(name=body.name, description=body.description)
    db.add(c)
    db.commit()
    return CollectionOut(id=c.id, name=c.name, description=c.description, document_count=0)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    collection: Annotated[str, Form(min_length=1, max_length=120)] = "General",
    title: Annotated[str | None, Form(max_length=300)] = None,
    tags: Annotated[str | None, Form(max_length=500)] = None,
    meta: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    col = get_or_create_collection(db, collection)
    tag_list = [t.strip()[:40] for t in (tags or "").split(",") if t.strip()][:30]
    try:
        ver = register_upload(
            db,
            settings,
            collection=col,
            src=file.file,
            filename=file.filename,
            title=title,
            tags=tag_list,
            meta=_parse_meta(meta),
        )
    except (ExtractionError, IngestError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _dispatch(request, db, ver)
    db.refresh(ver.document)
    return doc_out(ver.document)


class WebIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    collection: str = Field(default="Web", min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=30)


@router.post("/documents/web", response_model=DocumentOut, status_code=202)
def ingest_web(body: WebIn, request: Request, db: DbSession, settings: AppSettings) -> DocumentOut:
    """Fetch an approved public page (SSRF-protected) and ingest it as an untrusted source."""
    import io

    from sourceatlas.web.fetch import FetchBlocked, fetch

    try:
        page = fetch(
            body.url,
            allowed_domains=settings.web_allowed_domains or None,
            timeout=settings.web_timeout_seconds,
        )
    except FetchBlocked as exc:
        raise HTTPException(status_code=422, detail=f"URL rejected: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The page could not be fetched") from exc
    col = get_or_create_collection(db, body.collection)
    name = "page.html" if page.content_type != "text/plain" else "page.txt"
    try:
        ver = register_upload(
            db,
            settings,
            collection=col,
            src=io.BytesIO(page.body),
            filename=name,
            tags=body.tags,
            meta={"fetched_from": page.final_url},
        )
    except (ExtractionError, IngestError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ver.document.source_type, ver.document.source_uri = "web", page.final_url
    db.commit()
    _dispatch(request, db, ver)
    db.refresh(ver.document)
    return doc_out(ver.document)


@router.get("/web/search")
def web_search(
    q: Annotated[str, Query(min_length=2, max_length=300)], settings: AppSettings
) -> dict[str, Any]:
    if not settings.searxng_url:
        raise HTTPException(status_code=503, detail="Web search is not configured (SOURCEATLAS_SEARXNG_URL)")
    from sourceatlas.web.fetch import searxng

    try:
        return {"results": searxng(settings.searxng_url, q, timeout=settings.web_timeout_seconds)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Search provider unavailable") from exc


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    db: DbSession,
    collection: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    tag: str | None = None,
    status_: Annotated[
        Literal["pending", "processing", "ready", "failed"] | None, Query(alias="status")
    ] = None,
) -> list[DocumentOut]:
    stmt = select(Document).join(Collection).order_by(Document.created_at.desc())
    if collection:
        stmt = stmt.where(or_(Collection.name == collection, Collection.id == collection))
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    docs = [doc_out(d) for d in db.scalars(stmt)]
    if tag:
        docs = [d for d in docs if tag in d.tags]
    if status_:
        docs = [d for d in docs if d.status == status_]
    return docs


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(doc: DocumentDep) -> DocumentOut:
    return doc_out(doc)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(doc: DocumentDep, body: DocumentPatch, db: DbSession) -> DocumentOut:
    if body.title is not None:
        doc.title = body.title
    if body.tags is not None:
        doc.tags = [t[:40] for t in body.tags]
    if body.meta is not None:
        doc.meta = body.meta
    db.commit()
    return doc_out(doc)


@router.post("/documents/{document_id}/versions", response_model=DocumentOut, status_code=202)
def upload_version(
    request: Request,
    doc: DocumentDep,
    db: DbSession,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    try:
        ver = register_upload(
            db, settings, collection=doc.collection, src=file.file, filename=file.filename, document=doc
        )
    except (ExtractionError, IngestError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _dispatch(request, db, ver)
    db.refresh(doc)
    return doc_out(doc)


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut, status_code=202)
def reindex(request: Request, doc: DocumentDep, db: DbSession) -> DocumentOut:
    if not doc.versions:
        raise HTTPException(status_code=409, detail="Nothing to reindex")
    _dispatch(request, db, doc.versions[-1])
    db.refresh(doc)
    return doc_out(doc)


@router.delete("/documents/{document_id}", status_code=204)
def remove(doc: DocumentDep, db: DbSession, settings: AppSettings) -> None:
    delete_document(db, settings, doc)


@router.get("/documents/{document_id}/passages", response_model=list[PassageOut])
def passages(doc: DocumentDep, db: DbSession, version: int | None = None) -> list[PassageOut]:
    ver = next((v for v in doc.versions if v.version == version), None) if version else doc.current
    if ver is None:
        raise HTTPException(status_code=404, detail="Version not found")
    rows = db.scalars(select(Passage).where(Passage.version_id == ver.id).order_by(Passage.ordinal))
    return [PassageOut.model_validate(p, from_attributes=True) for p in rows]


@router.get("/documents/{document_id}/file")
def original_file(doc: DocumentDep, settings: AppSettings, version: int | None = None) -> FileResponse:
    ver = next((v for v in doc.versions if v.version == version), None) if version else doc.current
    if ver is None or not ver.storage_path:
        raise HTTPException(status_code=404, detail="File not found")
    path = (settings.storage_dir / ver.storage_path).resolve()
    if settings.storage_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Uploaded HTML is served as plain text so it can never execute in the app's origin.
    media = (
        "application/pdf"
        if ver.mime == "application/pdf"
        else ("text/plain; charset=utf-8" if ver.mime.startswith("text/") else ver.mime)
    )
    return FileResponse(
        path,
        media_type=media,
        filename=ver.filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("/passages/{passage_id}")
def passage(passage_id: str, db: DbSession, context: Annotated[int, Query(ge=0, le=3)] = 1) -> dict[str, Any]:
    p = db.get(Passage, passage_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Passage not found")
    near = db.scalars(
        select(Passage)
        .where(
            Passage.version_id == p.version_id,
            Passage.ordinal.between(p.ordinal - context, p.ordinal + context),
        )
        .order_by(Passage.ordinal)
    ).all()
    doc = db.get(Document, p.document_id)
    ver = db.get(DocumentVersion, p.version_id)
    assert doc and ver
    return {
        "passage": PassageOut.model_validate(p, from_attributes=True).model_dump(),
        "context": [PassageOut.model_validate(x, from_attributes=True).model_dump() for x in near],
        "document": {
            "id": doc.id,
            "title": doc.title,
            "version": ver.version,
            "filename": ver.filename,
            "mime": ver.mime,
            "meta": doc.meta,
            "source_uri": doc.source_uri,
        },
    }
