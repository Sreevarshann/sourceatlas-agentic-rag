from __future__ import annotations

from pathlib import Path

from sourceatlas.agent.evidence import claim_support
from sourceatlas.config import Settings
from sourceatlas.evaluation.benchmark import QUESTIONS, run
from sourceatlas.llm.fixture import FixtureProvider


def test_benchmark_subset_end_to_end(tmp_path: Path, database_url: str) -> None:
    s = Settings(environment="test", database_url=database_url, data_dir=tmp_path / "v", embedding_provider="hashing", llm_provider="fixture", log_level="WARNING")
    subset = [q for q in QUESTIONS if q.id in {"rotation", "return_window", "ceo_salary", "partner_discount"}]
    report = run(s, FixtureProvider, label="t", out_dir=tmp_path, questions=subset)
    sm = report["summary"]
    assert sm["documents"] == 8 and sm["retrieval"]["hybrid"]["recall_at_5"] == 1.0
    assert sm["conflict_detected"] == 1.0 and sm["injection_resisted"] == 1.0
    assert next(r for r in report["questions"] if r["id"] == "ceo_salary")["abstain"]
    assert (tmp_path / "latest-t.json").is_file()


def test_irrelevant_but_faithful_claim_is_rejected() -> None:
    p = ["The Halcyon Cloud Basic plan costs 4 dollars per month per hub."]
    s = claim_support("The Halcyon Cloud Basic plan costs 4 dollars per month per hub.", p, None, [None], question="How many offices does Halcyon have in Europe?")
    assert not s.supported and "does not address" in s.reason
