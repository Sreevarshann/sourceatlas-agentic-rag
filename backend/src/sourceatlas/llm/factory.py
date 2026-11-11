from __future__ import annotations

from sourceatlas.config import Settings
from sourceatlas.llm.base import LLMProvider, OllamaProvider, OpenAICompatibleProvider
from sourceatlas.llm.fixture import FixtureProvider


def make_llm(s: Settings) -> LLMProvider:
    if s.llm_provider == "fixture":
        return FixtureProvider()
    if s.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(s.llm_base_url, s.llm_model, s.llm_api_key, s.llm_timeout_seconds)
    return OllamaProvider(s.llm_base_url, s.llm_model, s.llm_timeout_seconds)
