# Evaluation

Implementation: `backend/src/sourceatlas/evaluation/benchmark.py` · run with `make evaluate` (live) / `make evaluate-fixture`. Raw reports: `eval/results/`.

**Corpus:** 8 SYNTHETIC documents for the fictional Halcyon Devices (PDF manual + newer version, conflicting 2024/2025 return policies, DOCX, HTML, TXT, meeting decision, a partner FAQ with a planted prompt injection). **Questions:** 13 answerable (gold evidence = file + required text), 2 unanswerable, 1 injection probe. Gold matching is independent of chunking and passage ids.

## Retrieval (latest runs)

| Method | Recall@5 (hashing) | MRR@10 (hashing) | Recall@5 (nomic) | MRR@10 (nomic) | Median latency (nomic) |
|---|---|---|---|---|---|
| vector | 0.929 | 0.845 | 1.000 | 0.836 | 15.0 ms |
| keyword | 1.000 | 0.917 | 1.000 | 0.952 | 4.9 ms |
| hybrid | 1.000 | 0.917 | 1.000 | 0.893 | 20.2 ms |

On this small corpus keyword search has the best MRR; semantic search is not assumed to win. Hybrid (RRF) keeps Recall@5 at 1.0 with both embedders.

*Observed anomaly:* keyword MRR differs between the two runs (0.917 vs 0.952) although keyword search does not use the embedder. Keyword ties are broken only by passage ordinal, which is not unique across documents, so equal `ts_rank_cd` scores can order differently between database instances. A fully deterministic tie-breaker (passage id) is a listed fix.

## Answers — live runs with qwen3:4b-instruct + nomic-embed-text (local Ollama)

Each run fixed problems found by the previous one; all three reports are kept.

| Run (UTC) | Answer correct | Citation correct | Groundedness | Abstention acc. | Conflict detected | Injection resisted | Median latency | Change before the run |
|---|---|---|---|---|---|---|---|---|
| 20261111T083858Z | 53.8% | 87.5% | 80.0% | 62.5% | 100.0% | 100.0% | 15.8 s | baseline |
| 20261111T114446Z | 69.2% | 90.0% | 100.0% | 75.0% | 100.0% | 100.0% | 9.0 s | negation compared per matching sentence (was: whole passage) |
| 20261111T125506Z | 92.3% | 95.8% | 88.5% | 87.5% | 100.0% | 100.0% | 12.6 s | planner collection guess no longer filters search; generation capped at 700 tokens |
| fixture (hashing + extractive heuristic, **not an LLM**) | 84.6% | 69.2% | 64.3% | 93.8% | 100.0% | 100.0% | 0.05 s | pipeline test |

## Failure analysis (latest live run)

* `password` — the model's JSON was truncated by the 700-token generation cap ("Model did not return JSON") → abstained. The cap bounds latency (earlier runs hit the 180 s timeout); a retry-on-truncation step is a future improvement.
* `inject_warranty` — the model merged two facts into one claim ("2-year warranty … water damage not covered"); per-sentence negation checking rejects such compound claims, so the system abstained. The injected "10 years" was never asserted.
* Earlier runs: 5 correct claims rejected by a whole-passage negation check (fixed); 3 Ollama timeouts from unbounded generation (fixed); one question answered from the wrong collection because the planner's guess was used as a hard filter (fixed).

## Metric definitions and limitations

* *answer correct*: a verified claim contains the expected key fact; *citation correct*: share of verified claims citing a gold passage; *groundedness*: share of drafted claims that passed verification; *abstention accuracy*: unanswerable → abstain and answerable → answer.
* 16 questions on one synthetic corpus, one small local model: these are not general accuracy claims. Verification is heuristic (see CITATION_VERIFICATION.md), not entailment.
