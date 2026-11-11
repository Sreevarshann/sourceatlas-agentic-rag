"""Relational + vector schema. One PostgreSQL database holds metadata, passages,
pgvector embeddings and full-text vectors, so hybrid retrieval is a single SQL query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Computed, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB().with_variant(JSON(), "sqlite"),
        list[Any]: JSONB().with_variant(JSON(), "sqlite"),
    }


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    documents: Mapped[list[Document]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(16))  # upload | web
    source_uri: Mapped[str | None] = mapped_column(Text, default=None)
    tags: Mapped[list[Any]] = mapped_column(default=list)
    # Optional structured metadata, e.g. {"effective_date": "2025-03-01", "policy_id": "refunds"}
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    collection: Mapped[Collection] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version"
    )

    @property
    def current(self) -> DocumentVersion | None:
        ready = [v for v in self.versions if v.status == "ready"]
        return ready[-1] if ready else (self.versions[-1] if self.versions else None)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str | None] = mapped_column(String(512), default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text, default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    passage_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    document: Mapped[Document] = relationship(back_populates="versions")


class Passage(Base):
    __tablename__ = "passages"
    __table_args__ = (
        Index("ix_passages_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_passages_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, default=None)
    section: Mapped[str | None] = mapped_column(String(300), default=None)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), default=None)
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(section, '') || ' ' || text)", persisted=True)
    )


class ResearchSession(Base):
    """A question, its verified answer, the evidence used and the recorded tool trace."""

    __tablename__ = "research_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(24), default="running")
    filters: Mapped[dict[str, Any]] = mapped_column(default=dict)
    answer: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    evidence: Mapped[list[Any]] = mapped_column(default=list)
    quarantined: Mapped[list[Any]] = mapped_column(default=list)
    trace: Mapped[list[Any]] = mapped_column(default=list)
    model_name: Mapped[str | None] = mapped_column(String(160), default=None)
    embedder: Mapped[str | None] = mapped_column(String(160), default=None)
    llm_usage: Mapped[dict[str, Any]] = mapped_column(default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
