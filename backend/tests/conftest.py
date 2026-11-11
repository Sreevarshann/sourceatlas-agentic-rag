"""Tests run against a REAL PostgreSQL + pgvector database (no SQLite stand-in).

Locally: `docker compose up -d db`. CI: a pgvector service container. Each test session
uses a dedicated database, recreated from scratch.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from sourceatlas.config import Settings
from sourceatlas.main import create_app

ADMIN_URL = os.environ.get(
    "SOURCEATLAS_TEST_ADMIN_URL",
    "postgresql+psycopg://sourceatlas:sourceatlas_local_only@127.0.0.1:55502/sourceatlas",
)
TEST_DB = "sourceatlas_test"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {TEST_DB}"))
    url = make_url(ADMIN_URL).set(database=TEST_DB).render_as_string(hide_password=False)
    yield url
    admin.dispose()


@pytest.fixture
def settings(tmp_path: Path, database_url: str) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        data_dir=tmp_path / "var",
        llm_provider="fixture",
        embedding_provider="hashing",
        log_level="WARNING",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        with app.state.engine.begin() as conn:  # isolate tests: empty all tables
            conn.execute(text("TRUNCATE collections, documents, document_versions, passages CASCADE"))
        yield c
