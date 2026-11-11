# SourceAtlas

**Explore knowledge. Trace every answer.**

SourceAtlas is an agentic RAG research engine: multi-step hybrid retrieval over PostgreSQL
(pgvector + full-text), evidence sufficiency checks, conflict detection between documents,
and answers whose every claim links to a verified source passage.

> **Status: early development.** See [PLAN.md](PLAN.md) and [PROGRESS.md](PROGRESS.md).

```bash
make db        # pgvector on 127.0.0.1:55502 (compose project "sourceatlas")
make setup
make test      # runs against the real Postgres
make dev-api   # http://127.0.0.1:8112/api/health
```
