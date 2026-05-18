from __future__ import annotations

from scripts.failure_case_logging_schema import (
    EXPLICIT_EMPTY_MARKER,
    EXPLICIT_NOT_SCORED_YET_MARKER,
    EXPLICIT_UNAVAILABLE_MARKER,
    EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
    build_promotion_review_record,
    validate_promotion_review_record,
)


def _base_record() -> dict:
    return {
        "run_id": "run_1",
        "artifact_label": "artifact_a",
        "example_id": "openai_gsm8k_1",
        "dataset": "openai/gsm8k",
        "provider": "cohere",
        "model": "command-a-03-2025",
        "method": "external_l1_max",
        "budget": 6,
        "seed": 20260501,
        "question": "Q",
        "prompt_text": "Prompt",
        "candidate_answer": "42",
        "candidate_trace": "trace",
        "parse_success": True,
        "parser_status": "ok",
        "parser_error": "",
        "status": "ok",
        "runtime_cap_reached": False,
        "error_type": "",
        "error_message": "",
        "discovery_tree_pointer": "outputs/x/tree.json",
        "node_expansion_order": [0, 1, 2],
        "final_nodes": [{"node_id": "n2"}],
        "selected_node_id": "n2",
        "prune_or_selection_reasons": ["max_support"],
        "candidate_pool_summary": {"size": 2},
        "candidate_pool_pointer": "outputs/x/pool.json",
        "call_count": 3,
        "prompt_tokens": 1200,
        "completion_tokens": 200,
        "total_tokens": 1400,
        "estimated_cost": 0.01,
        "latency_seconds": 3.2,
        "cost_timeline": [{"t": 0, "c": 0.003}],
        "verifier_scores": {"raw_proba_ready": 0.9},
        "raw_proba_ready": 0.9,
        "calibrated_percentile": 0.95,
        "gate_features": {"margin": 0.5},
        "gate_decision": "switch",
        "policy_family": "conservative_combo",
        "policy_thresholds": {"frontier_min": 0.85},
    }


def test_complete_success_record_is_enough_yes() -> None:
    rec = build_promotion_review_record(_base_record())
    out = validate_promotion_review_record(rec)
    assert out["enough_for_promotion_review"] == "yes"
    assert out["runtime_failure_reviewable"] == "yes"
    assert out["missing_required_fields"] == []
    assert out["missing_critical_fields"] == []


def test_runtime_cap_failure_with_explicit_empty_states_is_reviewable() -> None:
    raw = _base_record()
    raw.update(
        {
            "status": "runtime_cap",
            "runtime_cap_reached": True,
            "error_type": "RuntimeError",
            "error_message": "Global logical API call cap reached",
            "candidate_answer": None,
            "candidate_trace": None,
            "node_expansion_order": None,
            "prune_or_selection_reasons": None,
        }
    )
    rec = build_promotion_review_record(raw, fill_explicit_failure_state=True)
    assert rec["candidate_answer"] == EXPLICIT_EMPTY_MARKER
    assert rec["candidate_trace"] == EXPLICIT_EMPTY_MARKER
    assert rec["node_expansion_order"] == EXPLICIT_UNAVAILABLE_MARKER
    assert rec["prune_or_selection_reasons"] == EXPLICIT_UNAVAILABLE_MARKER
    out = validate_promotion_review_record(rec)
    assert out["runtime_failure_reviewable"] == "yes"
    assert out["enough_for_promotion_review"] in {"yes", "partial"}


def test_runtime_cap_failure_without_explicit_failure_state_is_not_reviewable() -> None:
    raw = _base_record()
    raw.update(
        {
            "status": "runtime_cap",
            "runtime_cap_reached": True,
            "error_type": "",
            "error_message": "",
            "candidate_answer": None,
            "candidate_trace": None,
            "node_expansion_order": None,
            "prune_or_selection_reasons": None,
        }
    )
    rec = build_promotion_review_record(raw, fill_explicit_failure_state=False)
    out = validate_promotion_review_record(rec)
    assert out["runtime_failure_reviewable"] == "no"
    assert out["enough_for_promotion_review"] == "no"


def test_missing_node_expansion_and_prune_reasons_is_partial_or_no() -> None:
    raw = _base_record()
    raw["node_expansion_order"] = None
    raw["prune_or_selection_reasons"] = None
    rec = build_promotion_review_record(raw, fill_explicit_failure_state=False)
    out = validate_promotion_review_record(rec)
    assert out["enough_for_promotion_review"] in {"partial", "no"}
    assert "node_expansion_order_or_unavailable" in out["missing_required_fields"]
    assert "prune_or_selection_reasons_or_unavailable" in out["missing_required_fields"]


def test_success_with_explicit_not_scored_and_unavailable_markers_is_yes() -> None:
    raw = _base_record()
    raw.pop("prompt_text", None)
    raw["prompt_hash"] = "question_sha256:abc123"
    raw["prune_or_selection_reasons"] = EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
    raw["verifier_scores"] = {}
    raw["verifier_scores_pointer"] = EXPLICIT_NOT_SCORED_YET_MARKER
    raw["raw_proba_ready"] = EXPLICIT_NOT_SCORED_YET_MARKER
    raw["calibrated_percentile"] = None
    rec = build_promotion_review_record(raw, fill_explicit_failure_state=False)
    out = validate_promotion_review_record(rec)
    assert out["enough_for_promotion_review"] == "yes"
    assert out["runtime_failure_reviewable"] == "yes"


def test_success_missing_prompt_score_and_verifier_fields_is_partial() -> None:
    raw = _base_record()
    raw.pop("prompt_text", None)
    raw.pop("prompt_pointer", None)
    raw.pop("prompt_hash", None)
    raw["verifier_scores"] = {}
    raw["verifier_scores_pointer"] = ""
    raw["raw_proba_ready"] = None
    raw["calibrated_percentile"] = None
    rec = build_promotion_review_record(raw, fill_explicit_failure_state=False)
    out = validate_promotion_review_record(rec)
    assert out["enough_for_promotion_review"] in {"partial", "no"}
    assert "prompt_text_or_pointer_or_hash" in out["missing_required_fields"]
    assert "verifier_scores_or_pointer" in out["missing_required_fields"]
    assert "raw_or_calibrated_score" in out["missing_required_fields"]


def test_offline_eval_fields_are_flagged_offline_only() -> None:
    raw = _base_record()
    raw["exact_match"] = 1
    raw["gold_answer"] = "42"
    raw["offline_eval_only"] = True
    rec = build_promotion_review_record(raw)
    out = validate_promotion_review_record(rec)
    assert sorted(out["offline_eval_only_fields_present"]) == ["exact_match", "gold_answer"]
    assert out["offline_eval_only_fields_flagged"] is True


def test_gold_and_exact_match_not_required_for_sufficiency() -> None:
    rec = build_promotion_review_record(_base_record())
    rec.pop("exact_match", None)
    rec.pop("gold_answer", None)
    out = validate_promotion_review_record(rec)
    assert out["enough_for_promotion_review"] == "yes"
    assert "exact_match" not in out["missing_required_fields"]
    assert "gold_answer" not in out["missing_required_fields"]


def test_schema_helper_has_no_provider_api_imports() -> None:
    import pathlib

    script_path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "failure_case_logging_schema.py"
    txt = script_path.read_text(encoding="utf-8").lower()
    assert "import cohere" not in txt
    assert "from cohere" not in txt
    assert "import openai" not in txt
    assert "from openai" not in txt
