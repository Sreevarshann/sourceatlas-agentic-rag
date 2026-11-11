"""Load the SYNTHETIC Halcyon Devices corpus (idempotent)."""

from __future__ import annotations

import io
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from sourceatlas.config import Settings, get_settings
from sourceatlas.db.models import Document, DocumentVersion
from sourceatlas.db.session import make_engine, make_sessionmaker, run_migrations
from sourceatlas.demo.corpus import documents
from sourceatlas.embed.providers import Embedder, make_embedder
from sourceatlas.ingest.service import get_or_create_collection, process_version, register_upload


def seed(db: Session, settings: Settings, embedder: Embedder) -> list[str]:
    loaded = []
    for d in documents():
        if db.scalars(select(DocumentVersion).where(DocumentVersion.filename == d.filename)).first():
            continue
        col = get_or_create_collection(db, d.collection)
        ver = register_upload(
            db,
            settings,
            collection=col,
            src=io.BytesIO(d.data),
            filename=d.filename,
            tags=d.tags,
            meta={**d.meta, "synthetic": True},
        )
        process_version(db, settings, embedder, ver.id)
        if d.new_version:
            doc = db.get(Document, ver.document_id)
            assert doc
            v2 = register_upload(
                db, settings, collection=col, src=io.BytesIO(d.new_version), filename=d.filename, document=doc
            )
            process_version(db, settings, embedder, v2.id)
        loaded.append(d.filename)
    return loaded


if __name__ == "__main__":
    s = get_settings()
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    eng = make_engine(s.database_url)
    run_migrations(eng)
    with make_sessionmaker(eng)() as db:
        print("seeded:", seed(db, s, make_embedder(s)) or "(already present)", file=sys.stderr)
