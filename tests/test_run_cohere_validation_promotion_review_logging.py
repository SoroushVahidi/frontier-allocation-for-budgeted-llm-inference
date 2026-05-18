from __future__ import annotations

from scripts.failure_case_logging_schema import (
    EXPLICIT_EMPTY_MARKER,
    EXPLICIT_UNAVAILABLE_MARKER,
)
from scripts.run_cohere_real_model_cost_normalized_validation import (
    build_promotion_review_fields_for_record,
)


def test_promotion_review_fields_keep_existing_row_semantics_for_scored_case() -> None:
    row = {
        "provider": "cohere",
        "model": "command-r",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 4,
        "method": "direct_reserve_semantic_frontier_v2",
        "example_id": "ex-1",
        "status": "scored",
        "error": "",
        "exact_match": 1,
        "question": "What is 2+2?",
        "gold_answer": "4",
        "final_answer_raw": "4",
        "final_answer_canonical": "4",
        "selected_answer_raw": "4",
        "selected_answer_canonical": "4",
        "parse_extraction_failure": 0,
        "result_metadata": {
            "action_trace": [
                {"action": "expand", "branch_id": "b0", "family_id": "fam0"},
                {"action": "expand", "branch_id": "b1", "family_id": "fam1"},
                {"action": "select", "branch_id": "b1", "selection_reason": "best score"},
            ],
            "answer_group_support_counts": {"4": 2},
        },
        "final_nodes": [
            {
                "branch_id": "b1",
                "reasoning_text": "2+2 is 4",
                "predicted_answer": "4",
                "predicted_answer_normalized": "4",
            }
        ],
        "cohere_logical_api_calls": 2,
        "input_tokens": 20,
        "output_tokens": 10,
        "total_tokens": 30,
        "latency_seconds": 0.2,
        "estimated_cost_usd": 0.01,
    }

    payload = build_promotion_review_fields_for_record(
        row,
        run_id="20260518T170000Z",
        artifact_label="cohere_real_model_cost_normalized_validation_20260518T170000Z",
    )

    assert row["status"] == "scored"
    assert row["final_answer_raw"] == "4"
    assert "promotion_review_record" in payload
    assert "promotion_review_validation" in payload
    review = payload["promotion_review_record"]
    validation = payload["promotion_review_validation"]
    assert review["candidate_answer"] == "4"
    assert review["candidate_trace"] == "2+2 is 4"
    assert review["selected_node_id"] == "b1"
    assert review["node_expansion_order"] == ["b0", "b1"]
    assert validation["runtime_failure_reviewable"] == "yes"
    assert "enough_for_promotion_review" in validation


def test_runtime_cap_failure_gets_explicit_failure_markers() -> None:
    row = {
        "provider": "cohere",
        "model": "command-r",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 4,
        "method": "direct_reserve_semantic_frontier_v2",
        "example_id": "ex-runtime-cap",
        "status": "failed",
        "error": "RuntimeError: Global logical API call cap reached",
        "exact_match": 0,
        "question": "Hard question",
        "gold_answer": "42",
        "selected_answer_raw": "",
        "selected_answer_canonical": "",
        "parse_extraction_failure": 1,
        "result_metadata": {},
        "final_nodes": [],
        "cohere_logical_api_calls": 4,
        "input_tokens": 50,
        "output_tokens": 0,
        "total_tokens": 50,
        "latency_seconds": 1.0,
        "estimated_cost_usd": 0.02,
    }

    payload = build_promotion_review_fields_for_record(
        row,
        run_id="20260518T170000Z",
        artifact_label="cohere_real_model_cost_normalized_validation_20260518T170000Z",
    )

    review = payload["promotion_review_record"]
    validation = payload["promotion_review_validation"]
    assert review["runtime_cap_reached"] is True
    assert review["candidate_answer"] == EXPLICIT_EMPTY_MARKER
    assert review["candidate_trace"] == EXPLICIT_EMPTY_MARKER
    assert review["node_expansion_order"] == EXPLICIT_UNAVAILABLE_MARKER
    assert review["prune_or_selection_reasons"] == EXPLICIT_UNAVAILABLE_MARKER
    assert validation["runtime_failure_reviewable"] == "yes"
