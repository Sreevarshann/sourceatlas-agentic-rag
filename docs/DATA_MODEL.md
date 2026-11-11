# Data model (PostgreSQL 16 + pgvector)

| Table | Key columns |
|---|---|
| `collections` | `name` (unique), `description` |
| `documents` | `collection_id`, `title`, `source_type` (upload/web), `source_uri`, `tags` (JSONB), `meta` (JSONB: `policy`, `effective_date`, `synthetic`, …) |
| `document_versions` | `version`, `filename`, `mime`, `sha256`, `size_bytes`, `storage_path`, `status` (pending/processing/ready/failed), `error`, `page_count`, `passage_count`, `embedding_model` |
| `passages` | `version_id`, `document_id`, `collection_id`, `ordinal`, `page`, `section`, `text`, `char_start/end`, `token_count`, `embedding vector(768)` (HNSW cosine), `tsv tsvector` (generated, GIN) |
| `research_sessions` | `question`, `parent_id` (follow-ups), `status`, `filters`, `answer` (claims + citations + support checks + conflicts + follow-ups), `evidence`, `quarantined`, `trace`, `model_name`, `embedder`, `llm_usage`, `duration_ms` |

Migrations: `backend/src/sourceatlas/migrations` (Alembic, applied at startup).
