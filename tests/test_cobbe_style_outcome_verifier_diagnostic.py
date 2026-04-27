from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import scripts.run_cobbe_style_outcome_verifier_diagnostic as cobbe


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_strict_source_fails_when_manifest_mismatch(tmp_path: Path) -> None:
    trace = tmp_path / "trace"
    cost = tmp_path / "cost"
    trace.mkdir()
    cost.mkdir()
    (trace / "manifest.json").write_text(json.dumps({"matched_examples": 12}), encoding="utf-8")
    (trace / "per_case_results.csv").write_text("dataset,example_id,seed,budget,gold_answer,external_l1_max_prediction,strict_f3_prediction\n", encoding="utf-8")
    (cost / "per_example_records.jsonl").write_text("", encoding="utf-8")
    (cost / "candidate_branch_table.csv").write_text("dataset,example_id,seed,budget\n", encoding="utf-8")
    (cost / "answer_group_table.csv").write_text("dataset,example_id,seed,budget\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        cobbe.ensure_strict_sources(trace, cost, required_matched_examples=30)


def test_no_gold_leak_in_input_features() -> None:
    audit = cobbe.no_gold_leak_feature_audit()
    bad = [r for r in audit if int(r["used_as_input"]) == 1 and int(r["contains_gold_term"]) == 1]
    assert bad == []


def test_leave_one_example_out_has_no_heldout_in_training() -> None:
    rows = [
        {"example_id": "e1", "question_text": "q1", "label_is_correct": 1, "branch_text_for_verifier": "a", **{f: 0.0 for f in cobbe.STRUCTURAL_FEATURES}},
        {"example_id": "e1", "question_text": "q1", "label_is_correct": 0, "branch_text_for_verifier": "b", **{f: 0.0 for f in cobbe.STRUCTURAL_FEATURES}},
        {"example_id": "e2", "question_text": "q2", "label_is_correct": 1, "branch_text_for_verifier": "c", **{f: 1.0 for f in cobbe.STRUCTURAL_FEATURES}},
        {"example_id": "e2", "question_text": "q2", "label_is_correct": 0, "branch_text_for_verifier": "d", **{f: 1.0 for f in cobbe.STRUCTURAL_FEATURES}},
    ]
    groups = cobbe.split_groups(rows, mode="example_id")
    for holdout in groups:
        train = [r for g, rr in groups.items() if g != holdout for r in rr]
        assert all(r["example_id"] != holdout for r in train)


def test_answer_bucket_aggregation_is_deterministic() -> None:
    case_rows = [
        {"example_id": "e1", "seed": 1, "budget": 4, "method": "m", "branch_id": "b1", "normalized_answer": "10", "support_count": 2, "family_count": 1},
        {"example_id": "e1", "seed": 1, "budget": 4, "method": "m", "branch_id": "b2", "normalized_answer": "11", "support_count": 1, "family_count": 1},
    ]
    scored = [
        {"example_id": "e1", "seed": 1, "budget": 4, "method": "m", "branch_id": "b1", "verifier_score": 0.9},
        {"example_id": "e1", "seed": 1, "budget": 4, "method": "m", "branch_id": "b2", "verifier_score": 0.2},
    ]
    p1, _ = cobbe.aggregate_bucket_scores(case_rows, scored, agg="max", beta=0.1, gamma=0.0)
    p2, _ = cobbe.aggregate_bucket_scores(case_rows, scored, agg="max", beta=0.1, gamma=0.0)
    assert p1 == p2 == "10"


def test_no_real_api_call_patterns_present() -> None:
    script_text = Path("scripts/run_cobbe_style_outcome_verifier_diagnostic.py").read_text(encoding="utf-8").lower()
    forbidden = ["openai.chat", "client.responses", "requests.post", "anthropic", "cohere.client", "google.generativeai"]
    assert all(tok not in script_text for tok in forbidden)


def test_summary_metrics_internal_consistency_tiny_fixture(tmp_path: Path) -> None:
    # minimal consistency check independent of model training
    decisions = [
        {"correct__external_l1_max": 1, "correct__strict_f3": 0, "correct__oracle_if_gold_present": 1, "correct__toy": 1},
        {"correct__external_l1_max": 0, "correct__strict_f3": 1, "correct__oracle_if_gold_present": 1, "correct__toy": 0},
    ]
    summary, best = cobbe.summarize_selectors(decisions)
    lookup = {r["selector"]: r["accuracy"] for r in summary}
    assert pytest.approx(lookup["external_l1_max"], rel=1e-9) == 0.5
    assert pytest.approx(lookup["strict_f3"], rel=1e-9) == 0.5
    assert pytest.approx(lookup["oracle_if_gold_present"], rel=1e-9) == 1.0
    assert best in lookup
