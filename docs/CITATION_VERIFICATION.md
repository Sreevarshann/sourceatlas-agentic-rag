# Citation verification

The drafter returns claims with passage references (`P1`, `P3`…). Each claim is checked
against the passages it cites; only claims that pass are shown as the answer. Rejected
claims are shown separately with the reason.

A claim is **supported** only if all of the following hold:

1. **Valid citations** — at least one cited ref exists among the evidence shown to the model
   (references like `P99` are reported as invalid).
2. **Exact numbers** — every number in the claim appears in a cited passage or in the
   header the model saw for it (title, version, section, effective date).
3. **Relevance** — the claim covers at least a third of the question's subject terms
   (framing words such as *current*, *policy*, *how long* are ignored). Added after the
   benchmark showed a faithful but off-topic sentence answering "How many offices…".
4. **Subject anchors** — at least half of the claim terms that also occur in the question
   must occur in the cited passage. Added after a live run accepted "Shipping takes 14
   days…" cited to a *refund* passage.
5. **Negation agreement** — a claim whose negation differs from its passage is rejected
   regardless of word overlap (high overlap makes a flipped negation more dangerous).
6. **Support** — lexical coverage of the claim's words by the passage ≥ 0.5, or embedding
   cosine similarity ≥ 0.75.

Answer status: `verified` (all claims supported), `partially_verified`, or `abstained`
(the model abstained or nothing could be verified).

## Limitations

These are deterministic heuristics, not entailment. They catch fabricated numbers, invalid
references, flipped negations and subject mismatches, but a paraphrase that changes
meaning without changing words, numbers or negation can pass. Thresholds were tuned on the
small synthetic corpus.
