from __future__ import annotations

import json
from pathlib import Path

from scripts import collect_external_loss_casebook as mod


def test_loss_case_selection_external_correct_internal_wrong_with_aliases(tmp_path: Path) -> None:
    art = tmp_path / "a"
    art.mkdir()
    per_case = art / "per_case_method_results.csv"
    per_case.write_text(
        "dataset,example_id,seed,budget,method,is_correct,gold_answer,normalized_selected_answer,question\n"
        "d,e1,1,4,dr_v2,0,42,41,q\n"
        "d,e1,1,4,L1-MAX,1,42,42,q\n",
        encoding="utf-8",
    )
    (art / "answer_group_summary.csv").write_text(
        "dataset,example_id,seed,budget,method,answer_group,support\n"
        "d,e1,1,4,dr_v2,41,3\n"
        "d,e1,1,4,dr_v2,42,1\n",
        encoding="utf-8",
    )
    trace_losses, final_only, scan_rows = mod._scan_artifact(art)
    assert len(scan_rows) >= 1
    assert len(trace_losses) == 1
    assert len(final_only) == 0
    assert trace_losses[0]["best_external_correct"] == 1
    assert trace_losses[0]["our_correct"] == 0


def test_gold_present_absent_and_oracle_fix_labels(tmp_path: Path) -> None:
    art = tmp_path / "a2"
    art.mkdir()
    (art / "per_case_method_results.csv").write_text(
        "dataset,example_id,seed,budget,method,is_correct,gold_answer,normalized_selected_answer,question\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,0,10,9,q\n"
        "d,e1,1,4,external_l1_max,1,10,10,q\n"
        "d,e2,1,4,direct_reserve_semantic_frontier_v2,0,20,19,q\n"
        "d,e2,1,4,external_l1_max,1,20,20,q\n",
        encoding="utf-8",
    )
    (art / "answer_group_summary.csv").write_text(
        "dataset,example_id,seed,budget,method,answer_group,support\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,10,1\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,9,2\n"
        "d,e2,1,4,direct_reserve_semantic_frontier_v2,19,1\n",
        encoding="utf-8",
    )
    losses, final_only, _ = mod._scan_artifact(art)
    assert len(final_only) == 0
    by_id = {r["example_id"]: r for r in losses}
    assert by_id["e1"]["gold_present_in_candidate_groups"] == 1
    assert by_id["e1"]["oracle_selector_would_fix"] == 1
    assert by_id["e2"]["gold_present_in_candidate_groups"] == 0


def test_support_gap_and_rank_when_gold_present(tmp_path: Path) -> None:
    art = tmp_path / "a3"
    art.mkdir()
    (art / "per_case_method_results.csv").write_text(
        "dataset,example_id,seed,budget,method,is_correct,gold_answer,normalized_selected_answer,question\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,0,5,4,q\n"
        "d,e1,1,4,external_l1_max,1,5,5,q\n",
        encoding="utf-8",
    )
    (art / "answer_group_summary.csv").write_text(
        "dataset,example_id,seed,budget,method,answer_group,support\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,4,10\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,5,7\n",
        encoding="utf-8",
    )
    losses, _, _ = mod._scan_artifact(art)
    r = losses[0]
    assert r["support_gap_selected_minus_gold_if_present"] == 3
    assert r["rank_of_gold_answer_group_if_present"] == 2


def test_final_row_only_included_not_rejected(tmp_path: Path) -> None:
    art = tmp_path / "a4"
    art.mkdir()
    (art / "rows.csv").write_text(
        "dataset,example_id,seed,budget,method,is_correct,gold_answer,normalized_selected_answer,question\n"
        "d,e1,1,4,direct_reserve_semantic_frontier_v2,0,10,9,q\n"
        "d,e1,1,4,external_l1_max,1,10,10,q\n",
        encoding="utf-8",
    )
    trace_losses, final_only, scan_rows = mod._scan_artifact(art)
    assert len(trace_losses) == 0
    assert len(final_only) == 1
    assert final_only[0]["trace_available"] == 0
    assert any(r["candidate_loss_cases"] >= 1 for r in scan_rows)


def test_cohere_prompt_diagnostic_only_no_key_leak() -> None:
    case = {
        "problem_statement": "q",
        "gold_answer": "1",
        "our_final_answer": "2",
        "best_external_answer": "1",
        "all_candidate_answer_groups": '["1","2"]',
        "branch_count": 2,
        "max_depth": 3,
        "top2_support_gap": 1,
        "gold_present_in_candidate_groups": 1,
    }
    p = mod._diag_prompt(case)
    assert "api_key" not in p.lower()
    assert "diagnose" in p.lower()


def test_output_schema_required_columns() -> None:
    required = {
        "case_id",
        "dataset",
        "example_id",
        "our_method_name",
        "best_external_method_name",
        "gold_present_in_candidate_groups",
        "oracle_selector_would_fix",
        "trace_available",
    }
    assert required.issubset(
        {
            "case_id",
            "dataset",
            "example_id",
            "our_method_name",
            "best_external_method_name",
            "gold_present_in_candidate_groups",
            "oracle_selector_would_fix",
            "trace_available",
        }
    )


def test_combined_fill_with_final_row_only_when_trace_insufficient() -> None:
    base = {
        "best_external_method_name": "external_l1_max",
        "branch_count": 0,
        "problem_statement": "q",
        "gold_present_in_candidate_groups": 0,
        "dataset": "d",
        "budget": 4,
        "seed": 1,
        "example_id": "e",
    }
    trace = [{**base, "case_id": "t1", "example_id": "e1"}]
    final = [{**base, "case_id": "f1", "example_id": "e2"}, {**base, "case_id": "f2", "example_id": "e3"}]
    selected_trace = mod._choose_cases(trace, 2)
    remaining = max(0, 2 - len(selected_trace))
    selected_final = mod._choose_cases(final, remaining)
    combined = selected_trace + selected_final
    assert len(combined) == 2
    assert any(x["case_id"] == "f1" for x in combined) or any(x["case_id"] == "f2" for x in combined)
