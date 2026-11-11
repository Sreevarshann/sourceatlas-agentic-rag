BACKEND := backend
.PHONY: setup db db-down dev-api test lint typecheck fmt
setup:
	cd $(BACKEND) && uv sync
db:
	docker compose up -d db
db-down:
	docker compose down
dev-api:
	cd $(BACKEND) && uv run uvicorn sourceatlas.main:app --reload --host 127.0.0.1 --port 8112
test:
	cd $(BACKEND) && uv run pytest -m "not live"
lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
typecheck:
	cd $(BACKEND) && uv run mypy
fmt:
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .

.PHONY: seed evaluate evaluate-fixture test-live
seed:
	cd $(BACKEND) && uv run python -m sourceatlas.demo.seed
# Real models: qwen3:4b-instruct + nomic-embed-text via Ollama (uses database sourceatlas_eval).
evaluate:
	cd $(BACKEND) && uv run python -m sourceatlas.evaluation.benchmark --mode live
# Deterministic pipeline benchmark (hashing embedder + extractive fixture; not semantic, not an LLM).
evaluate-fixture:
	cd $(BACKEND) && uv run python -m sourceatlas.evaluation.benchmark --mode fixture
test-live:
	cd $(BACKEND) && uv run pytest -m live -s
