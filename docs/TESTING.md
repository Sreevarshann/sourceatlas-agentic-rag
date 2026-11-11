# Testing

* `make test` — pytest against a **real PostgreSQL 16 + pgvector** database (no SQLite
  stand-in): extraction with generated PDF/DOCX files, chunking, hashing embedder, document
  lifecycle (dedup, versions, background processing, reindex, delete, safe serving),
  hybrid retrieval and RRF math, the research graph with the fixture provider and an
  adversarial "fabricator" model, conflict detection, injection quarantine, streaming,
  evidence graph, SSRF protections, and a benchmark subset.
* `make test-live` — the same research flow with qwen3:4b-instruct + nomic-embed-text
  (marked `live`, excluded from CI).
* `make evaluate` / `make evaluate-fixture` — benchmark (see EVALUATION.md).
* Frontend: ESLint, `tsc`, Vitest component tests, Playwright E2E on an isolated stack.

The fixture provider is an extractive heuristic and the hashing embedder is lexical; both
exist for deterministic CI and are labelled wherever their output is stored.
