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
