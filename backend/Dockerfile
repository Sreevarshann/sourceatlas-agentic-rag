FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev && useradd -m -u 10001 app && mkdir -p /data && chown app /data
USER app
ENV SOURCEATLAS_DATA_DIR=/data
EXPOSE 8112
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8112/api/health')"
CMD ["uv", "run", "--no-sync", "uvicorn", "sourceatlas.main:app", "--host", "0.0.0.0", "--port", "8112"]
