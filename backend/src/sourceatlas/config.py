from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOURCEATLAS_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3102"])

    database_url: str = "postgresql+psycopg://sourceatlas:sourceatlas_local_only@127.0.0.1:55502/sourceatlas"
    data_dir: Path = Path("./var")
    max_upload_bytes: int = 25 * 1024 * 1024

    llm_provider: Literal["ollama", "openai_compatible", "fixture"] = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b-instruct"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 180.0

    # "hashing" is a deterministic feature-hashing embedder for CI, NOT a semantic model.
    embedding_provider: Literal["ollama", "hashing"] = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # Process uploads synchronously in the request (tests / CLI). Default: background worker.
    ingest_inline: bool = False
    chunk_tokens: int = 220
    chunk_overlap: int = 40

    eval_results_dir: Path = Path("../eval/results")
    searxng_url: str | None = None
    web_allowed_domains: list[str] = Field(default_factory=list)
    web_timeout_seconds: float = 10.0

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "documents"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
