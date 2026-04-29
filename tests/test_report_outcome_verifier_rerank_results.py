from __future__ import annotations

import json
from pathlib import Path

from scripts.report_outcome_verifier_rerank_results import (
    build_report,
    compute_accuracy_table,
    compute_claim_safety,
    compute_main_question_summary,
    compute_paired_wtl,
)


def _row(method: str, ex: str, exact: int, *, gold_in_tree: int | None = None, md: dict | None = None) -> dict:
    r = {
        "provider": "cohere",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 4,
        "method": method,
        "example_id": ex,
        "scored": 1,
        "exact_match": exact,
        "total_tokens": 100,
        "estimated_cost_usd": 0.1,
        "latency_seconds": 1.0,
        "parse_extraction_failure": 0,
        "final_nodes": [{"x": 1}],
        "result_metadata": md or {},
    }
    if gold_in_tree is not None:
        r["gold_in_tree"] = gold_in_tree
    return r


def test_accuracy_and_paired_and_main_question_metrics():
    rows = [
        _row("external_l1_max", "e1", 1),
        _row("external_l1_max", "e2", 1),
        _row("direct_reserve_semantic_frontier_v2", "e1", 0, gold_in_tree=1),
        _row("direct_reserve_semantic_frontier_v2", "e2", 1, gold_in_tree=1),
        _row(
            "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
            "e1",
            1,
            md={"ov_rerank_gold_present_in_candidates": 1, "ov_rerank_recovered_present_not_selected": 1},
        ),
        _row(
            "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
            "e2",
            0,
            md={"ov_rerank_gold_present_in_candidates": 1, "ov_rerank_recovered_present_not_selected": 0},
        ),
    ]
    by_method = {}
    for r in rows:
        by_method.setdefault(r["method"], []).append(r)
    acc = compute_accuracy_table(by_method)
    acc_map = {r["method"]: r for r in acc}
    assert acc_map["external_l1_max"]["accuracy"] == 1.0
    assert acc_map["direct_reserve_semantic_frontier_v2"]["accuracy"] == 0.5
    assert acc_map["direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"]["accuracy"] == 0.5

    rows_by_key = {}
    for r in rows:
        key = (r["provider"], r["dataset"], r["seed"], r["budget"], r["example_id"])
        rows_by_key.setdefault(key, {})[r["method"]] = r
    paired = compute_paired_wtl(
        rows_by_key,
        "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
        "direct_reserve_semantic_frontier_v2",
    )
    assert paired["wins_a"] == 1
    assert paired["losses_a"] == 1
    assert paired["ties"] == 0

    mq = compute_main_question_summary(rows_by_key)
    assert mq["l1_correct_dr_v2_wrong_total"] == 1
    assert mq["recovered_by_ov_reranker"] == 1


def test_claim_safety_incomplete_and_negative():
    incomplete = [
        {"method": "external_l1_max", "scored_count": 99, "accuracy": 0.8},
        {"method": "direct_reserve_semantic_frontier_v2", "scored_count": 100, "accuracy": 0.6},
        {"method": "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "scored_count": 100, "accuracy": 0.7},
    ]
    out = compute_claim_safety(incomplete, 100)
    assert out["classification"] == "incomplete_not_claim_safe"

    negative = [
        {"method": "external_l1_max", "scored_count": 100, "accuracy": 0.8},
        {"method": "direct_reserve_semantic_frontier_v2", "scored_count": 100, "accuracy": 0.6},
        {"method": "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "scored_count": 100, "accuracy": 0.6},
    ]
    out2 = compute_claim_safety(negative, 100)
    assert out2["classification"] == "diagnostic_negative"


def test_build_report_handles_missing_selector_fields(tmp_path: Path):
    artifact = tmp_path / "outputs" / "cohere_real_model_cost_normalized_validation_SYNTH"
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "manifest.json").write_text(
        json.dumps(
            {
                "providers": ["cohere"],
                "models": {"cohere": "command-r-plus-08-2024"},
                "datasets": ["openai/gsm8k"],
                "budgets": [4],
                "seeds": [11],
                "methods": [
                    "external_l1_max",
                    "direct_reserve_semantic_frontier_v2",
                    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
                    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
                ],
                "target_scored_per_slice": 100,
            }
        ),
        encoding="utf-8",
    )
    rows = [
        _row("external_l1_max", "e1", 1),
        _row("direct_reserve_semantic_frontier_v2", "e1", 0, gold_in_tree=0),
        _row("direct_reserve_semantic_frontier_v2_selection_fix_v1", "e1", 0),
        _row("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "e1", 0, md={}),
    ]
    with (artifact / "per_example_records.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    report_path = tmp_path / "docs" / "report.md"
    written = build_report(artifact_dir=artifact, run_timestamp="SYNTH", report_path=report_path)
    assert written.exists()
    summary = json.loads((artifact / "ov_rerank_summary.json").read_text(encoding="utf-8"))
    assert "selector_fields_missing" in summary
    assert summary["claim_safety"]["classification"] == "incomplete_not_claim_safe"
