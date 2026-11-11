from __future__ import annotations

import itertools
import math

from sourceatlas.embed.providers import HashingEmbedder
from sourceatlas.ingest.chunk import build_document_text, chunk_segments, count_tokens
from sourceatlas.ingest.extract import Segment


def test_chunks_respect_page_boundaries_and_budget() -> None:
    sent = "The refund window is fourteen days from delivery. "
    segs = [
        Segment(sent * 30, page=1, section="Refunds"),
        Segment("Short page two.", page=2, section="Exchanges"),
    ]
    chunks = chunk_segments(segs, max_tokens=60, overlap=10)
    assert all(c.token_count <= 60 for c in chunks)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[-1].text == "Short page two." and chunks[-1].section == "Exchanges"
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_offsets_point_into_document_text() -> None:
    segs = [Segment("Alpha one. Beta two. Gamma three.", page=1), Segment("Delta four.", page=2)]
    text = build_document_text(segs)
    for c in chunk_segments(segs, max_tokens=4, overlap=0):
        assert text[c.char_start : c.char_end].strip() == c.text


def test_overlap_repeats_context_but_always_advances() -> None:
    segs = [Segment(" ".join(f"Sentence number {i} ends here." for i in range(40)))]
    chunks = chunk_segments(segs, max_tokens=30, overlap=10)
    assert len(chunks) > 3
    assert any(a.text.split(".")[-2].strip() in b.text for a, b in itertools.pairwise(chunks))
    assert all(b.char_start > a.char_start for a, b in itertools.pairwise(chunks))


def test_giant_sentence_is_split() -> None:
    chunks = chunk_segments([Segment("word " * 1000)], max_tokens=100, overlap=0)
    assert len(chunks) >= 10 and max(c.token_count for c in chunks) <= 100


def test_hashing_embedder_is_deterministic_and_normalised() -> None:
    e = HashingEmbedder(768)
    a, b = e.embed_documents(["refund window fourteen days"])[0], e.embed_query("refund window fourteen days")
    assert a == b and len(a) == 768 and math.isclose(sum(x * x for x in a), 1.0)
    near = e.embed_query("the refund window")
    far = e.embed_query("kubernetes cluster autoscaling")
    dot = lambda u, v: sum(x * y for x, y in zip(u, v, strict=True))  # noqa: E731
    assert dot(a, near) > dot(a, far)


def test_count_tokens() -> None:
    assert count_tokens("Hello, world!") == 4
