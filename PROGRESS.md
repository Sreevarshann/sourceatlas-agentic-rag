# SourceAtlas — Progress

| # | Milestone | Commit | Pushed | Checks |
|---|---|---|---|---|
| 1 | Foundation: settings, JSON logging, app factory, Postgres + pgvector schema (HNSW + GIN + generated tsvector), Alembic, compose stack, real-DB tests | `2ff7d5d` | ✔ verified | ruff ✔ · mypy strict ✔ · pytest 3/3 against pgvector/pg16 |
| 2 | Extraction: PDF (page + outline provenance, encrypted/oversized rejected), DOCX (heading hierarchy, tables, zip guard), Markdown/TXT sections, HTML (scripts/nav dropped); magic-byte validation; content-free errors | see git log | ✔ | pytest 16 passed (real reportlab PDFs + python-docx files) |
