# Deployment

`docker compose up -d --build` (project `sourceatlas`) runs `db` (pgvector, localhost:55502),
`api` (:8112) and `web` (:3102), all bound to localhost; Ollama is the host's
(`host.docker.internal:11434`). Configure via `SOURCEATLAS_*` (see `.env.example`). The local
database password in compose is for local use only — override `POSTGRES_PASSWORD` and
`SOURCEATLAS_DATABASE_URL` anywhere else. For multiple API instances, replace the in-process
ingestion worker with a queue (e.g. Redis + RQ/Arq) — state is already persisted per version.
