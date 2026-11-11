"""Embedding providers.

* ``OllamaEmbedder``: local semantic embeddings (default ``nomic-embed-text``, 768-d), with
  the model's ``search_document:`` / ``search_query:`` task prefixes.
* ``HashingEmbedder``: deterministic feature hashing of word uni/bi-grams. It is NOT a
  semantic model; it exists so CI can exercise indexing and retrieval without weights.
  It is labelled ``hashing-v1`` wherever results are stored or shown.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
from typing import Protocol

import httpx

from sourceatlas.config import Settings


class EmbeddingError(RuntimeError):
    pass


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, dim: int, timeout: float = 120.0, batch: int = 32) -> None:
        self.name, self.dim, self.batch = f"ollama:{model}", dim, batch
        self._model = model
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(inputs), self.batch):
            try:
                r = self._client.post(
                    "/api/embed",
                    json={"model": self._model, "input": inputs[i : i + self.batch], "truncate": True},
                )
                r.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingError(f"Embedding request failed: {type(exc).__name__}") from exc
            vecs = r.json().get("embeddings") or []
            if len(vecs) != len(inputs[i : i + self.batch]) or any(len(v) != self.dim for v in vecs):
                raise EmbeddingError("Embedding model returned an unexpected shape")
            out.extend(vecs)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([f"search_document: {t}" for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"search_query: {text}"])[0]


_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "by",
        "with",
        "as",
        "at",
        "it",
        "this",
        "that",
        "from",
    ]
)


class HashingEmbedder:
    def __init__(self, dim: int = 768) -> None:
        self.name, self.dim = "hashing-v1", dim

    def _vec(self, text: str) -> list[float]:
        words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
        feats = words + [f"{a}_{b}" for a, b in itertools.pairwise(words)]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def make_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "hashing":
        return HashingEmbedder(settings.embedding_dim)
    return OllamaEmbedder(settings.llm_base_url, settings.embedding_model, settings.embedding_dim)
