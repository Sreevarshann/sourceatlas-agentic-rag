# Key decisions

1. **One Postgres for metadata, vectors and full text** — hybrid retrieval in SQL, one backup,
   transactional reindexing; pgvector HNSW is fast enough at this scale.
2. **RRF for fusion** — rank-based, no score calibration between cosine and ts_rank.
3. **Claims, not paragraphs** — answers are lists of claims so each can be verified and cited.
4. **Deterministic verification over LLM-as-judge** — reproducible, explainable reasons, no
   extra model latency; limitations documented.
5. **Sanitise rather than drop injected passages** — live testing showed dropping lost real
   content.
6. **The model's collection guess is a hint, not a filter** — a hard filter hid the right
   documents in live evaluation.
7. **Bounded agent** — ≤ 3 retrieval rounds, ≤ 3 queries, ≤ 2 conflict judgements, capped
   generation; latency fell from ~190 s to ~13 s median.
8. **Local-first** — Ollama models; OpenAI-compatible adapter for larger models; no paid API.
