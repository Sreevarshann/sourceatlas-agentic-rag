from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sourceatlas import __version__
from sourceatlas.api import documents, health, research, search
from sourceatlas.api.middleware import SSENoTransform
from sourceatlas.config import Settings, get_settings
from sourceatlas.db.session import make_engine, make_sessionmaker, run_migrations
from sourceatlas.embed.providers import make_embedder
from sourceatlas.ingest.service import Processor
from sourceatlas.logging import configure_logging

log = logging.getLogger("sourceatlas")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        run_migrations(engine)
        log.info("startup", extra={"environment": settings.environment})
        yield
        app.state.processor.shutdown()
        engine.dispose()

    app = FastAPI(title="SourceAtlas API", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.embedder = make_embedder(settings)
    app.state.processor = Processor(app.state.sessionmaker, settings, app.state.embedder)
    app.add_middleware(SSENoTransform)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(research.router, prefix="/api")
    return app


app = create_app()
