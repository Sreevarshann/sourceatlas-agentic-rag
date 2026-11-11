"""Deterministic FIXTURE provider (not a language model).

It produces search queries from question keywords and drafts *extractive* answers: each
claim is the best-matching sentence of a retrieved passage, cited to that passage. This
lets CI exercise the graph, citation verification and conflict handling reproducibly.
Answers produced with it are labelled ``fixture``.
"""

from __future__ import annotations

import re
from typing import Any

from sourceatlas.llm.base import Task, Usage

STOP = frozenset(
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
        "what",
        "which",
        "who",
        "how",
        "when",
        "where",
        "why",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "about",
        "tell",
        "me",
        "please",
        "our",
        "we",
        "you",
        "your",
    ]
)


def keywords(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


class FixtureProvider:
    name, model = "fixture", "fixture-extractive-v1"

    def __init__(self) -> None:
        self.usage = Usage()

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.usage.calls += 1
        q = payload.get("question", "")
        if task == "understand":
            kw = keywords(q)
            compare = bool(
                re.search(r"\b(compare|differ|difference|changed|conflict|versus|vs|contradict)\b", q, re.I)
            )
            return {
                "intent": "comparison" if compare else ("out_of_scope" if not kw else "factual"),
                "queries": [q, " ".join(kw)] if kw else [q],
                "collections": [],
            }
        if task == "reformulate":
            kw = keywords(q)
            return {"queries": [" ".join(kw[: max(1, len(kw) // 2)]), " ".join(kw[len(kw) // 2 :])]}
        if task == "conflict":
            return {
                "conflict": True,
                "explanation": "The passages state different values for the same topic.",
            }
        # draft: extractive — best sentence per top passage
        kws = set(keywords(q))
        claims = []
        for p in payload.get("evidence", [])[:3]:
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p["text"]) if s.strip()]
            best = max(sents, key=lambda s: len(kws & set(keywords(s))), default="")
            if best and kws & set(keywords(best)):
                claims.append({"text": best, "citations": [p["ref"]]})
        if not claims:
            return {
                "abstain": True,
                "reason": "The retrieved sources do not address the question.",
                "claims": [],
                "follow_ups": [],
            }
        return {
            "abstain": False,
            "reason": None,
            "claims": claims,
            "follow_ups": [f"What exceptions apply to {' '.join(sorted(kws)[:3])}?"],
        }
