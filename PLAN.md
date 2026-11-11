# SourceAtlas — Plan

Ports: API 8112, web 3102, Postgres 55502 (verified free 2026-11-11; 8012 is another project's).

## Architecture (target)
- **PostgreSQL 16 + pgvector**: collections, documents, versions, passages (768-d
  embeddings, HNSW cosine index, generated `tsvector` with GIN), research sessions.
- **Ingestion**: PDF (PyMuPDF, page provenance), DOCX, TXT, Markdown (section headings),
  HTML, approved public web pages (SSRF-safe fetch). Validation, sha256 dedup, versions,
  background processing state, reindex, delete.
- **Chunking**: structure-aware (page/section), token-bounded with overlap; char offsets.
- **Embeddings**: Ollama `nomic-embed-text` (local); deterministic hashing embedder for CI
  (labelled, not semantic).
- **Retrieval**: vector, full-text, reciprocal rank fusion, metadata/document filters,
  thresholds, neighbour-passage expansion.
- **Agent (LangGraph)**: understand → classify → select collections → generate queries →
  retrieve → sufficiency check → reformulate (bounded) → rerank → conflict detection →
  draft with citations → verify citation support → answer or abstain.
- **Citations**: passage id, document, version, page/section, excerpt; claim-level
  support verification (lexical + embedding similarity, recorded).
- **Web research**: optional SearXNG; URL validation, private-IP blocking, domain allow-list,
  timeouts, extraction; web text treated as untrusted evidence.
- **Frontend** (warm porcelain / indigo / turquoise, editorial serif): Knowledge Library,
  Document Viewer (PDF.js page + passage highlight), Research Studio, Evidence Graph
  (React Flow), Conflict view, Retrieval Evaluation dashboard (Plotly).
- **Evaluation**: Recall@K, MRR, citation correctness, groundedness, abstention,
  conflict handling, injection resistance, latency, per retrieval method.

## Milestones
1. Foundation (FastAPI, Postgres + pgvector schema, migrations, real-DB tests) ← current
2. Document storage + extraction pipeline
3. Chunking + embeddings + indexing
4. Keyword / vector / hybrid retrieval
5. Agent orchestration + citation validation
6. Conflict analysis
7. Web research (optional)
8. Frontend: library, viewer, studio, evidence graph
9. Evaluation suite + dashboard
10. E2E, docs, screenshots, CI
