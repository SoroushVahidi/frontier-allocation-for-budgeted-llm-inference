from __future__ import annotations

from scripts.failure_case_logging_schema import (
    EXPLICIT_EMPTY_MARKER,
    EXPLICIT_NOT_SCORED_YET_MARKER,
    EXPLICIT_UNAVAILABLE_MARKER,
    EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
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
    assert str(review["prompt_hash"]).startswith("question_sha256:")
    assert review["prune_or_selection_reasons"][0]["action"] == "select"
    assert review["verifier_scores_pointer"] == EXPLICIT_NOT_SCORED_YET_MARKER
    assert review["raw_proba_ready"] == EXPLICIT_NOT_SCORED_YET_MARKER
    assert validation["runtime_failure_reviewable"] == "yes"
    assert validation["enough_for_promotion_review"] == "yes"


def test_scored_row_without_selection_trace_gets_explicit_unavailable_marker() -> None:
    row = {
        "provider": "cohere",
        "model": "command-r",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 4,
        "method": "direct_reserve_semantic_frontier_v2",
        "example_id": "ex-2",
        "status": "scored",
        "error": "",
        "exact_match": 1,
        "question": "What is 2+3?",
        "gold_answer": "5",
        "final_answer_raw": "5",
        "final_answer_canonical": "5",
        "selected_answer_raw": "5",
        "selected_answer_canonical": "5",
        "parse_extraction_failure": 0,
        "result_metadata": {
            "action_trace": [{"action": "expand", "branch_id": "b0", "family_id": "fam0"}],
            "answer_group_support_counts": {"5": 1},
        },
        "final_nodes": [
            {
                "branch_id": "b0",
                "reasoning_text": "2+3 is 5",
                "predicted_answer": "5",
                "predicted_answer_normalized": "5",
            }
        ],
        "cohere_logical_api_calls": 1,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "latency_seconds": 0.1,
        "estimated_cost_usd": 0.005,
    }

    payload = build_promotion_review_fields_for_record(
        row,
        run_id="20260518T170000Z",
        artifact_label="cohere_real_model_cost_normalized_validation_20260518T170000Z",
    )
    review = payload["promotion_review_record"]
    validation = payload["promotion_review_validation"]
    assert review["prune_or_selection_reasons"] == EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
    assert review["verifier_scores_pointer"] == EXPLICIT_NOT_SCORED_YET_MARKER
    assert review["raw_proba_ready"] == EXPLICIT_NOT_SCORED_YET_MARKER
    assert validation["enough_for_promotion_review"] == "yes"


def test_external_method_success_row_gets_node_expansion_unavailable_marker() -> None:
    """External methods have no action_trace; node_expansion_order must be explicitly marked."""
    row = {
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 6,
        "method": "external_l1_max",
        "example_id": "openai_gsm8k_190",
        "status": "scored",
        "error": "",
        "exact_match": 1,
        "question": "How many apples?",
        "gold_answer": "7",
        "final_answer_raw": "7",
        "final_answer_canonical": "7",
        "selected_answer_raw": "7",
        "selected_answer_canonical": "7",
        "parse_extraction_failure": 0,
        "result_metadata": {},  # no action_trace — external method
        "final_nodes": [
            {
                "branch_id": "b0",
                "reasoning_text": "The answer is 7",
                "predicted_answer": "7",
                "predicted_answer_normalized": "7",
            }
        ],
        "cohere_logical_api_calls": 1,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "latency_seconds": 0.5,
        "estimated_cost_usd": 0.005,
    }

    payload = build_promotion_review_fields_for_record(
        row,
        run_id="20260518T220000Z",
        artifact_label="cohere_real_model_cost_normalized_validation_20260518T220000Z",
    )
    review = payload["promotion_review_record"]
    validation = payload["promotion_review_validation"]
    assert review["node_expansion_order"] == EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
    assert "node_expansion_order_or_unavailable" not in validation["missing_required_fields"]
    assert validation["enough_for_promotion_review"] == "yes"
    assert validation["runtime_failure_reviewable"] == "yes"


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
