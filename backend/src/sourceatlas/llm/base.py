"""LLM providers. Output is always a *proposal*: plans are validated, drafted claims are
checked against cited passages before reaching the user."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

Task = Literal["understand", "reformulate", "draft", "conflict"]


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    log: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str
    model: str
    usage: Usage

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]: ...


def parse_json(text: str) -> dict[str, Any]:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip().strip("`")
    t = re.sub(r"^json\s*", "", t)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise LLMError("Model did not return JSON") from None
        try:
            obj = json.loads(t[a : b + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned malformed JSON") from exc
    if not isinstance(obj, dict):
        raise LLMError("Model JSON was not an object")
    return obj


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.model, self.usage = model, Usage()
        self._c = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            r = self._c.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "options": {"temperature": 0, "seed": 11, "num_ctx": 8192, "num_predict": 700},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {type(exc).__name__}") from exc
        d = r.json()
        ms = (time.perf_counter() - t0) * 1000
        self.usage.calls += 1
        self.usage.prompt_tokens += int(d.get("prompt_eval_count", 0))
        self.usage.completion_tokens += int(d.get("eval_count", 0))
        self.usage.latency_ms += ms
        self.usage.log.append({"task": task, "ms": round(ms, 1)})
        return parse_json(d.get("message", {}).get("content", ""))


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: str | None, timeout: float) -> None:
        self.model, self.usage = model, Usage()
        self._c = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            r = self._c.post(
                "/v1/chat/completions",
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": task, "schema": schema},
                    },
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        self.usage.calls += 1
        self.usage.latency_ms += (time.perf_counter() - t0) * 1000
        return parse_json(content)
