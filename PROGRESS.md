# SourceAtlas — Progress

| # | Milestone | Commit | Pushed | Checks |
|---|---|---|---|---|
| 1 | Foundation: settings, JSON logging, app factory, Postgres + pgvector schema (HNSW + GIN + generated tsvector), Alembic, compose stack, real-DB tests | `2ff7d5d` | ✔ verified | ruff ✔ · mypy strict ✔ · pytest 3/3 against pgvector/pg16 |
| 2 | Extraction: PDF (page + outline provenance, encrypted/oversized rejected), DOCX (heading hierarchy, tables, zip guard), Markdown/TXT sections, HTML (scripts/nav dropped); magic-byte validation; content-free errors | `79ecdcd` | ✔ verified | pytest 16 passed (real reportlab PDFs + python-docx files) |
| 3 | Chunking (page/section-bounded, sentence-aware, overlap, char offsets), embeddings (Ollama nomic-embed-text; deterministic hashing embedder for CI, labelled), ingestion lifecycle (sha256 dedup, versions, background processing state, reindex, delete), library API (collections, documents, passages, safe original-file serving) | `8ea6882` | ✔ verified | pytest 30 passed on pgvector |
| 4 | Retrieval: pgvector cosine (HNSW), Postgres FTS (websearch tsquery, OR-ed terms, ts_rank_cd), RRF hybrid (k=60), collection/document/tag/metadata filters, current-version-only, min-score threshold, neighbour expansion; `/api/search`; CI with pgvector service | `7c8db87` | ✔ verified | pytest 40 passed; CI run 42969696574 green |
| 5 | Agentic research graph (LangGraph: understand → retrieve → assess → bounded reformulate → rerank → conflicts → draft → verify), claim-level citation verification (numbers incl. header dates, question-anchor terms, negation, lexical/semantic support), conflict detection (same policy id / same topic + differing numbers or negation, newer by effective_date, LLM-confirmed), prompt-injection sanitising, research sessions + SSE + evidence graph API | `f1d4db3` | ✔ verified | pytest 54 passed; **live** (qwen3:4b-instruct + nomic-embed-text): 3/3 questions verified, 9–20 s |
| 6 | Web research: SSRF-safe fetch (scheme/port/credential checks, all resolved IPs must be public incl. metadata/CGNAT ranges, IP pinning, re-validated redirects, content-type + size caps, optional allow-list), `/documents/web` ingest marked as untrusted web source, optional SearXNG client | `3568237` | ✔ | pytest 73 passed |
| 7 | SYNTHETIC Halcyon Devices corpus (8 docs: PDF manual + newer version, conflicting return policies, DOCX, HTML, TXT, meeting note, planted injection) + evaluation suite (Recall@5/MRR@10 per method, answer/citation correctness, groundedness, abstention, conflicts, injection, latency); question-relevance check added after the benchmark exposed an off-topic 'answer' | see git log | ✔ | pytest 75 passed; fixture eval stored |

### Findings from live testing (fixed in this milestone)
- Similarity-only conflict detection flagged unrelated short policies (credentials vs refunds) → now requires same policy id, or similarity AND shared subject terms.
- A claim citing the effective date from the evidence header was wrongly rejected → numbers in the header the model saw are accepted.
- "Shipping takes 14 days" was accepted when cited to a refund passage → question-anchor term check.
- Quarantining a whole injected passage discarded legitimate content → instruction-like sentences are stripped, the rest kept and marked `sanitized`.
- A negated claim with high word overlap was accepted → negation mismatch now always fails.
- Latency fell from ~190 s to ~15 s (fewer LLM conflict judgements, smaller context).
