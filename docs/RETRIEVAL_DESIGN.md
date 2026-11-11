# Retrieval design

* **Chunking** — passages never cross a page (PDF) or heading section (DOCX/MD/HTML);
  sentences are packed up to ~220 tokens with ~40 tokens overlap; very long sentences are
  split. Character offsets are stored for each passage.
* **Embeddings** — `nomic-embed-text` (768-d) through the local Ollama server with its
  `search_document:` / `search_query:` prefixes. The section heading is prepended to the
  passage text before embedding. CI uses a deterministic feature-hashing embedder
  (`hashing-v1`), which is lexical and not semantic.
* **Vector search** — pgvector cosine distance on an HNSW index.
* **Keyword search** — `websearch_to_tsquery` terms OR-ed together (so partial matches
  rank) and ranked with `ts_rank_cd`; phrases are preserved, `-term` exclusions are not
  supported in this mode; stop-word-only queries return nothing.
* **Hybrid** — reciprocal rank fusion with k = 60 over a 4× candidate pool. RRF needs no
  calibration between cosine similarity and ts_rank. Each hit keeps its per-method ranks
  and scores, which the UI shows.
* **Filters** — collection (id or name), document ids, tags (JSONB containment), exact
  metadata keys (e.g. `policy`, `effective_date`), minimum score.
* **Rerank** — heuristic: `100 × RRF + question-term coverage`. No cross-encoder is used
  (a future improvement); this is labelled in the trace.

Measured results per method are in [EVALUATION.md](EVALUATION.md). Semantic search is
not assumed to be better: keyword search matched or beat hashing-vector retrieval in the
fixture run, and the hybrid is evaluated separately.
