# SourceAtlas — Progress

| # | Milestone | Commit | Pushed | Checks |
|---|---|---|---|---|
| 1 | Foundation: settings, JSON logging, app factory, Postgres + pgvector schema (HNSW + GIN + generated tsvector), Alembic, compose stack, real-DB tests | `2ff7d5d` | ✔ verified | ruff ✔ · mypy strict ✔ · pytest 3/3 against pgvector/pg16 |
| 2 | Extraction: PDF (page + outline provenance, encrypted/oversized rejected), DOCX (heading hierarchy, tables, zip guard), Markdown/TXT sections, HTML (scripts/nav dropped); magic-byte validation; content-free errors | `79ecdcd` | ✔ verified | pytest 16 passed (real reportlab PDFs + python-docx files) |
| 3 | Chunking (page/section-bounded, sentence-aware, overlap, char offsets), embeddings (Ollama nomic-embed-text; deterministic hashing embedder for CI, labelled), ingestion lifecycle (sha256 dedup, versions, background processing state, reindex, delete), library API (collections, documents, passages, safe original-file serving) | see git log | ✔ | pytest 30 passed on pgvector |
