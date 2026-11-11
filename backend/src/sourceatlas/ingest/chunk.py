"""Structure-aware chunking: passages never cross a page or section boundary, are bounded
by an approximate token budget, break at sentence ends when possible, and record exact
character offsets into the extracted segment text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sourceatlas.ingest.extract import Segment

_TOKEN = re.compile(r"\w+|[^\w\s]")
_SENT_END = re.compile(r"(?<=[.!?])\s+|\n\n+")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    page: int | None
    section: str | None
    char_start: int  # offset into the concatenated document text (see build_document_text)
    char_end: int
    token_count: int


def count_tokens(text: str) -> int:
    return len(_TOKEN.findall(text))


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENT_END.finditer(text):
        if m.start() > start:
            spans.append((start, m.start()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def chunk_segments(segments: list[Segment], max_tokens: int = 220, overlap: int = 40) -> list[Chunk]:
    chunks: list[Chunk] = []
    offset = 0
    for seg in segments:
        text = seg.text
        spans = _sentence_spans(text)
        # split very long sentences on token boundaries
        units: list[tuple[int, int, int]] = []
        for s, e in spans:
            n = count_tokens(text[s:e])
            if n <= max_tokens:
                units.append((s, e, n))
                continue
            words = list(re.finditer(r"\S+", text[s:e]))
            for i in range(0, len(words), max_tokens // 2):
                part = words[i : i + max_tokens // 2]
                ps, pe = s + part[0].start(), s + part[-1].end()
                units.append((ps, pe, count_tokens(text[ps:pe])))
        i = 0
        while i < len(units):
            j, total = i, 0
            while j < len(units) and (total + units[j][2] <= max_tokens or j == i):
                total += units[j][2]
                j += 1
            s, e = units[i][0], units[j - 1][1]
            body = text[s:e].strip()
            if body:
                chunks.append(
                    Chunk(
                        len(chunks), body, seg.page, seg.section, offset + s, offset + e, count_tokens(body)
                    )
                )
            if j >= len(units):
                break
            # step back to keep ~overlap tokens of context, but always advance
            back, k = 0, j
            while k - 1 > i and back + units[k - 1][2] <= overlap:
                k -= 1
                back += units[k][2]
            i = max(k, i + 1)
        offset += len(text) + 2
    return chunks


def build_document_text(segments: list[Segment]) -> str:
    """The text that chunk char offsets refer to (segments joined by blank lines)."""
    return "\n\n".join(s.text for s in segments)
