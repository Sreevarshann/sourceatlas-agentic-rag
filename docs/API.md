# API (base `/api`)

| Endpoint | Purpose |
|---|---|
| `GET /health` | DB, pgvector version, embedding + LLM provider |
| `GET/POST /collections` | List / create collections |
| `POST /documents` (multipart `file`, `collection`, `title`, `tags`, `meta` JSON) | Upload (202; background processing unless inline) |
| `POST /documents/web` `{url, collection, tags}` | SSRF-safe page ingestion |
| `GET /documents?collection&q&tag&status` · `GET/PATCH/DELETE /documents/{id}` | Library |
| `POST /documents/{id}/versions` · `POST /documents/{id}/reindex` | Versioning / re-embedding |
| `GET /documents/{id}/passages?version` · `GET /documents/{id}/file?version` · `GET /passages/{id}?context` | Provenance and originals |
| `POST /search` `{query, method, k, min_score, filters}` | vector / keyword / hybrid retrieval |
| `POST /research` · `POST /research/stream` (SSE) | Agentic research (events: session, stage, retrieval, evidence, conflicts, answer, done, error) |
| `GET /research` · `GET /research/{id}` · `GET /research/{id}/graph` | History, session, evidence graph |
| `GET /web/search?q` | Optional SearXNG search (503 if not configured) |
| `GET /evaluation` | Stored benchmark reports |
