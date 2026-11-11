from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from sourceatlas.config import Settings
from sourceatlas.db.models import Document
from sourceatlas.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


def _settings(request: Request) -> Settings:
    s: Settings = request.app.state.settings
    return s


AppSettings = Annotated[Settings, Depends(_settings)]


def load_document(document_id: str, db: DbSession) -> Document:
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return d


DocumentDep = Annotated[Document, Depends(load_document)]
