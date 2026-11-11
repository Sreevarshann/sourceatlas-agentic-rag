"""Deterministic evidence checks: prompt-injection quarantine, sufficiency, reranking,
claim-to-citation support, and conflict candidates. Every decision is recorded with the
reason, so the UI can show *why* a passage or claim was accepted or rejected."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sourceatlas.llm.fixture import keywords

INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)?\s*(instructions|prompts|rules)"
    r"|you\s+are\s+now\s+|system\s+prompt|act\s+as\s+(an?\s+)?(ai|assistant|admin)|reveal\s+(your|the)\s+(prompt|instructions)"
    r"|do\s+not\s+cite|respond\s+only\s+with|new\s+instructions\s*:",
    re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")
NEGATION = re.compile(r"\b(not|no|never|non-?\w+|without|cannot|prohibited)\b", re.I)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION.search(text))


def strip_injection(text: str) -> tuple[str, list[str]]:
    """Remove instruction-like sentences, keeping the rest of the passage as evidence."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    kept = [x for x in sents if not INJECTION.search(x)]
    removed = [x for x in sents if INJECTION.search(x)]
    return " ".join(kept).strip(), removed


def _stem(w: str) -> str:
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").replace("$", "").rstrip("%") for n in NUMBER.findall(text)}


def coverage(question: str, texts: list[str]) -> float:
    kw = set(keywords(question))
    if not kw:
        return 0.0
    found = set().union(*(set(keywords(t)) for t in texts)) if texts else set()
    # crude stemming: plural/singular
    norm = {w.rstrip("s") for w in found}
    return sum(1 for w in kw if w in found or w.rstrip("s") in norm) / len(kw)


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


@dataclass
class Support:
    supported: bool
    lexical: float
    semantic: float
    numbers_ok: bool
    reason: str


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Question-framing words that describe *what is asked* rather than the subject.
ANCHOR_IGNORE = frozenset(
    [
        "current",
        "latest",
        "new",
        "old",
        "now",
        "today",
        "window",
        "period",
        "policy",
        "policies",
        "rule",
        "rules",
        "time",
        "long",
        "many",
        "much",
        "often",
        "number",
        "amount",
        "maximum",
        "minimum",
        "allowed",
        "required",
        "need",
        "needs",
    ]
)


def claim_support(
    claim: str,
    passages: list[str],
    claim_vec: list[float] | None,
    passage_vecs: list[list[float] | None],
    *,
    question: str = "",
    headers: list[str] | None = None,
    lexical_min: float = 0.5,
    semantic_min: float = 0.75,
) -> Support:
    """A claim is supported only if (1) every number in it appears in a cited passage or
    its header (title, version, section, effective date: the context the model saw),
    (2) at least half of the claim terms that are also question terms ("anchor", e.g. *shipping*) occurs
    in the cited passage, (3) its negation agrees with the passage, and (4) its content
    words are covered (lexical) or it is semantically close to a cited passage."""
    if not passages:
        return Support(False, 0.0, 0.0, False, "no valid citation")
    ctext = " ".join(passages)
    header = " ".join(headers or [])
    date_parts = {part for d in _DATE.findall(header) for part in d.split("-")}
    allowed = numbers(ctext) | numbers(header) | date_parts | {x.lstrip("0") for x in date_parts}
    missing = numbers(claim) - allowed
    # numbers are checked exactly above; lexical coverage is over the words only
    lex = coverage(NUMBER.sub(" ", claim), [*passages, header])
    sem = max((cosine(claim_vec, v) for v in passage_vecs), default=0.0)
    if missing:
        return Support(False, lex, sem, False, f"number(s) {sorted(missing)} not in cited passage")
    subject = {_stem(w) for w in keywords(question)} - ANCHOR_IGNORE
    if subject:
        relevance = len(subject & {_stem(w) for w in keywords(claim)}) / len(subject)
        # A claim can be faithful to its passage yet not address the question
        # (benchmark: an "offices in Europe" question answered with a pricing sentence).
        if relevance < 1 / 3:
            return Support(
                False,
                lex,
                sem,
                True,
                f"claim does not address the question (covers {relevance:.0%} of its subject terms)",
            )
    anchors = {_stem(w) for w in keywords(claim)} & {_stem(w) for w in keywords(question)}
    present = {_stem(w) for w in keywords(ctext + " " + header)}
    anchors = {x for x in anchors if not x.isdigit() and x not in ANCHOR_IGNORE}
    missing_anchor = sorted(x for x in anchors if x not in present)
    # At least half of the anchors must occur: tolerates paraphrase ("refund window")
    # but rejects claims about a different subject (e.g. "shipping" cited to a refund passage).
    if anchors and len(missing_anchor) > len(anchors) / 2:
        return Support(False, lex, sem, True, f"claim term(s) {missing_anchor} not in cited passage")
    # High word overlap makes a flipped negation MORE dangerous, never less.
    # Compare against the passage sentence that best matches the claim, not the whole
    # passage (live eval: "warranty is 2 years" was rejected because the same passage
    # also said "water damage is not covered").
    sentences = [x for p in passages for x in re.split(r"(?<=[.!?])\s+", p) if x.strip()]
    best = max(sentences, key=lambda x: coverage(NUMBER.sub(" ", claim), [x]), default=ctext)
    if bool(NEGATION.search(claim)) != bool(NEGATION.search(best)):
        return Support(False, lex, sem, True, "negation mismatch with cited passage")
    ok = lex >= lexical_min or sem >= semantic_min
    return Support(
        ok, lex, sem, True, "supported" if ok else f"low overlap ({lex:.2f}) and similarity ({sem:.2f})"
    )


def rerank(question: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Heuristic reranker: fused retrieval score blended with question-term coverage."""
    for h in hits:
        h["coverage"] = round(coverage(question, [h["text"], h.get("section") or ""]), 3)
        h["rerank_score"] = round(h["score"] * 100 + h["coverage"], 4)
    return sorted(hits, key=lambda h: -h["rerank_score"])


def _parse_date(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


@dataclass
class ConflictCandidate:
    a: dict[str, Any]
    b: dict[str, Any]
    kind: str
    detail: str
    newer: str | None = None
    signals: dict[str, Any] = field(default_factory=dict)


def conflict_candidates(
    hits: list[dict[str, Any]], vecs: dict[str, list[float] | None], *, sim_min: float = 0.6
) -> list[ConflictCandidate]:
    """Pairs of passages from *different documents* about the same topic whose numbers or
    negation differ, or that share a policy id with different effective dates."""
    out: list[ConflictCandidate] = []
    for i, a in enumerate(hits):
        for b in hits[i + 1 :]:
            if a["document_id"] == b["document_id"]:
                continue
            ma, mb = a.get("meta", {}), b.get("meta", {})
            same_policy = bool(ma.get("policy") and ma.get("policy") == mb.get("policy"))
            topic = max(
                cosine(vecs.get(a["passage_id"]), vecs.get(b["passage_id"])), coverage(a["text"], [b["text"]])
            )
            if not same_policy and topic < sim_min:
                continue
            na, nb = numbers(a["text"]), numbers(b["text"])
            diff_numbers = bool(na and nb and na != nb)
            diff_neg = bool(NEGATION.search(a["text"])) != bool(NEGATION.search(b["text"]))
            if not (diff_numbers or diff_neg):
                continue
            da, db_ = _parse_date(ma.get("effective_date")), _parse_date(mb.get("effective_date"))
            newer = None
            if da and db_ and da != db_:
                newer = a["passage_id"] if da > db_ else b["passage_id"]
            detail = (
                f"numbers differ ({sorted(na)} vs {sorted(nb)})"
                if diff_numbers
                else "one passage negates the other"
            )
            out.append(
                ConflictCandidate(
                    a,
                    b,
                    "same_policy" if same_policy else "same_topic",
                    detail,
                    newer,
                    {
                        "topic_similarity": round(topic, 3),
                        "effective_dates": [ma.get("effective_date"), mb.get("effective_date")],
                    },
                )
            )
    return out
