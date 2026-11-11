#!/usr/bin/env bash
# Isolated API for Playwright: fresh database, deterministic hashing embedder + fixture LLM.
set -euo pipefail
cd "$(dirname "$0")/.."
ADMIN="${SOURCEATLAS_TEST_ADMIN_URL:-postgresql+psycopg://sourceatlas:sourceatlas_local_only@127.0.0.1:55502/sourceatlas}"
E2E_URL="${ADMIN%/*}/sourceatlas_e2e"
uv run python - "$ADMIN" <<'PY'
import sys
from sqlalchemy import create_engine, text
e = create_engine(sys.argv[1], isolation_level="AUTOCOMMIT")
with e.connect() as c:
    c.execute(text("DROP DATABASE IF EXISTS sourceatlas_e2e WITH (FORCE)"))
    c.execute(text("CREATE DATABASE sourceatlas_e2e"))
PY
rm -rf var-e2e
export SOURCEATLAS_DATABASE_URL="$E2E_URL" SOURCEATLAS_DATA_DIR=var-e2e SOURCEATLAS_EMBEDDING_PROVIDER=hashing SOURCEATLAS_LLM_PROVIDER=fixture SOURCEATLAS_INGEST_INLINE=true
uv run python -m sourceatlas.demo.seed
exec uv run uvicorn sourceatlas.main:app --host 127.0.0.1 --port 8192 --log-level warning
