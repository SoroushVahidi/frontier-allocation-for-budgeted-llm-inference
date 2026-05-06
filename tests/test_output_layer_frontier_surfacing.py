"""Offline tests for frontier-aware final-answer surfacing (no API, no gold in controller paths)."""

from __future__ import annotations

from types import SimpleNamespace

from experiments.output_layer_repair import (
    apply_controller_committed_surfacing_for_evaluation,
    augment_final_nodes_with_metadata_frontier,
    choose_repair_answer,
    effective_answer_raw_from_node,
    gold_in_tree_from_nodes,
    resolve_selected_group_hint_from_metadata,
)


def test_resolve_hint_from_final_answer_without_selected_group() -> None:
    md = {"final_answer": "42", "answer_group_support_counts": {"__unknown__": 1}}
    assert resolve_selected_group_hint_from_metadata(md, dataset="openai/gsm8k") == "42"


def test_augment_final_nodes_adds_direct_hybrid_without_frontier_executed() -> None:
    registry = [{"branch_id": "direct_reserve_0", "predicted_answer": "6", "reasoning_text": "x", "score": 0.5}]
    md = {
        "frontier_executed": False,
        "selector_candidate_pool": [
            {
                "branch_id": "direct_hybrid_seed_0",
                "predicted_answer": "42",
                "reasoning_text": "seed trace",
                "source_metadata": "direct_hybrid_seed",
                "branch_score": 0.5,
            }
        ],
    }
    out = augment_final_nodes_with_metadata_frontier(registry, md)
    assert any(n.get("branch_id") == "direct_hybrid_seed_0" for n in out)
    assert any(n.get("source_metadata") == "direct_hybrid_seed" for n in out)


def test_augment_final_nodes_adds_pal_candidate_without_frontier_executed() -> None:
    registry = [{"branch_id": "direct_reserve_0", "predicted_answer": "1", "reasoning_text": "", "score": 0.5}]
    md = {
        "frontier_executed": False,
        "selector_candidate_pool": [
            {
                "branch_id": "pal_seed_0",
                "predicted_answer": "200",
                "reasoning_text": "answer=200",
                "source_metadata": "pal_seed",
                "branch_score": 0.9,
            }
        ],
    }
    out = augment_final_nodes_with_metadata_frontier(registry, md)
    assert any(n.get("branch_id") == "pal_seed_0" for n in out)
    assert any(n.get("source_metadata") == "pal_seed" for n in out)


def test_augment_final_nodes_adds_pal_empty_code_retry_candidate_without_frontier_executed() -> None:
    registry = [{"branch_id": "direct_reserve_0", "predicted_answer": "1", "reasoning_text": "", "score": 0.5}]
    md = {
        "frontier_executed": False,
        "selector_candidate_pool": [
            {
                "branch_id": "pal_empty_code_retry_0",
                "predicted_answer": "200",
                "reasoning_text": "answer=200",
                "source_metadata": "pal_empty_code_retry",
                "branch_score": 0.95,
            }
        ],
    }
    out = augment_final_nodes_with_metadata_frontier(registry, md)
    assert any(n.get("branch_id") == "pal_empty_code_retry_0" for n in out)
    assert any(n.get("source_metadata") == "pal_empty_code_retry" for n in out)


def test_augment_final_nodes_updates_existing_pal_branch_with_executed_answer() -> None:
    registry = [
        {"branch_id": "pal_seed_0", "predicted_answer": "180", "reasoning_text": "", "score": 0.3},
    ]
    md = {
        "frontier_executed": False,
        "selector_candidate_pool": [
            {
                "branch_id": "pal_seed_0",
                "predicted_answer": "200",
                "reasoning_text": "answer=200",
                "source_metadata": "pal_seed",
                "branch_score": 0.9,
            }
        ],
    }
    out = augment_final_nodes_with_metadata_frontier(registry, md)
    assert len(out) == 1
    assert out[0].get("predicted_answer") == "200"
    assert out[0].get("source_metadata") == "pal_seed"
    assert gold_in_tree_from_nodes(out, "200", dataset="openai/gsm8k") == 1


def test_augment_final_nodes_adds_frontier_action_trace_rows() -> None:
    registry = [
        {"branch_id": "direct_reserve_0", "predicted_answer": None, "reasoning_text": "x", "score": 0.5},
        {"branch_id": "direct_reserve_1", "predicted_answer": None, "reasoning_text": "y", "score": 0.5},
    ]
    md = {
        "frontier_executed": True,
        "frontier_metadata": {
            "action_trace": [
                {"action": "expand", "branch_id": "fb0", "response_text": '{"action":"continue"}', "extracted_answer": "7"},
                {"action": "expand", "branch_id": "fb1", "response_text": "{}", "extracted_answer": ""},
            ]
        },
    }
    out = augment_final_nodes_with_metadata_frontier(registry, md)
    assert len(out) == 4
    assert any(str(n.get("branch_id", "")).startswith("fb0") for n in out)
    assert any(n.get("source_metadata") == "frontier_action_trace" for n in out)


def test_choose_repair_uses_reasoning_when_predicted_answer_empty() -> None:
    nodes = [
        {
            "branch_id": "direct_reserve_0",
            "predicted_answer": None,
            "reasoning_text": "Therefore the result is #### 99 ####.",
            "score": 0.4,
        }
    ]
    rep = choose_repair_answer(
        final_nodes=nodes,
        selected_group_hint="99",
        dataset="openai/gsm8k",
        enable_rescue=False,
    )
    assert rep.get("surfaced_final_answer_raw") == "99"


def test_effective_answer_prefers_trace_extracted_answer() -> None:
    n = {
        "branch_id": "z",
        "predicted_answer": None,
        "trace_extracted_answer": "12",
        "reasoning_text": "noise #### 3 ####",
    }
    assert effective_answer_raw_from_node(n, dataset="openai/gsm8k") == "12"


def test_effective_answer_uses_numeric_leaf_after_reasoning_extraction() -> None:
    n = {
        "branch_id": "b",
        "predicted_answer": None,
        "reasoning_text": "",
        "numeric_leaf_value": "12",
        "numeric_leaf_status": "equation_progress",
    }
    assert effective_answer_raw_from_node(n, dataset="openai/gsm8k") == "12"


def test_gold_in_tree_uses_effective_answer() -> None:
    nodes = [
        {"branch_id": "a", "predicted_answer": None, "reasoning_text": "#### 70000 ####", "score": 0.5},
    ]
    assert gold_in_tree_from_nodes(nodes, "70000", dataset="openai/gsm8k") == 1


def test_external_l1_style_selected_group_still_surfaces() -> None:
    nodes = [
        {"branch_id": "b1", "predicted_answer": "8", "reasoning_text": "", "score": 0.9},
    ]
    rep = choose_repair_answer(
        final_nodes=nodes,
        selected_group_hint="8",
        dataset="openai/gsm8k",
        enable_rescue=False,
    )
    assert rep.get("surfaced_final_answer_raw") == "8"


def test_apply_controller_surfacing_overrides_wrong_repair_surface() -> None:
    nodes = [
        {
            "branch_id": "direct_reserve_0",
            "predicted_answer": "1",
            "reasoning_text": '{"confidence": 1}',
            "score": 0.1,
        }
    ]
    rep = choose_repair_answer(
        final_nodes=nodes,
        selected_group_hint="1",
        dataset="openai/gsm8k",
        enable_rescue=False,
    )
    assert rep.get("surfaced_final_answer_raw") == "1"
    md = {"final_answer": "1300", "gold_should_not_matter": "9999"}
    out = apply_controller_committed_surfacing_for_evaluation(md, rep, dataset="openai/gsm8k")
    assert out["final_answer_source"] == "controller_metadata_final_answer"
    assert out["surfaced_final_answer_raw"] == "1300"
    assert out["chosen_final_node_answer_canonical"] == "1300"
    assert out["repair_answer_raw"] == "1"


def test_apply_controller_agrees_with_selected_canonical_when_present() -> None:
    rep = {
        "surfaced_final_answer_raw": "1",
        "surfaced_final_answer_canonical": "1",
        "chosen_final_node_answer_raw": "1",
        "chosen_final_node_answer_canonical": "1",
    }
    md = {"final_answer": "45000"}
    out = apply_controller_committed_surfacing_for_evaluation(md, rep, dataset="openai/gsm8k")
    assert out["surfaced_final_answer_canonical"] == out["chosen_final_node_answer_canonical"] == "45000"


def test_apply_controller_absent_preserves_repair() -> None:
    nodes = [
        {"branch_id": "b1", "predicted_answer": "8", "reasoning_text": "", "score": 0.9},
    ]
    rep = choose_repair_answer(
        final_nodes=nodes,
        selected_group_hint="8",
        dataset="openai/gsm8k",
        enable_rescue=False,
    )
    out = apply_controller_committed_surfacing_for_evaluation({}, rep, dataset="openai/gsm8k")
    assert out["final_answer_source"] == "repair_layer"
    assert out["surfaced_final_answer_raw"] == "8"


def test_evaluate_with_diagnostics_pipeline_with_augmented_nodes() -> None:
    from scripts.run_cohere_real_model_cost_normalized_validation import evaluate_with_diagnostics

    registry = [
        {"branch_id": "direct_reserve_0", "predicted_answer": None, "reasoning_text": "", "score": 0.5},
    ]
    md = {
        "frontier_executed": True,
        "final_answer": "15",
        "selected_group": "15",
        "frontier_metadata": {
            "action_trace": [
                {"action": "expand", "branch_id": "f0", "response_text": "{}", "extracted_answer": "15"},
            ]
        },
    }
    result = SimpleNamespace(metadata=md)
    merged = augment_final_nodes_with_metadata_frontier(registry, md)
    diag = evaluate_with_diagnostics(result, "openai/gsm8k", "15", merged, True)
    assert diag["parse_extraction_failure"] == 0
    assert diag["exact_match"] == 1
    assert diag.get("final_answer_source") == "controller_metadata_final_answer"


def test_pal_overlay_exact_implies_gold_in_tree_when_pal_candidate_in_pool() -> None:
    from scripts.run_cohere_real_model_cost_normalized_validation import evaluate_with_diagnostics

    registry = [{"branch_id": "direct_reserve_0", "predicted_answer": "1", "reasoning_text": "", "score": 0.5}]
    md = {
        "frontier_executed": False,
        "final_answer": "200",
        "selected_group": "200",
        "selector_candidate_pool": [
            {
                "branch_id": "pal_seed_0",
                "predicted_answer": "200",
                "reasoning_text": "answer=200",
                "source_metadata": "pal_seed",
                "branch_score": 0.9,
            }
        ],
    }
    result = SimpleNamespace(metadata=md)
    merged = augment_final_nodes_with_metadata_frontier(registry, md)
    diag = evaluate_with_diagnostics(result, "openai/gsm8k", "200", merged, True)
    assert diag["exact_match"] == 1
    assert diag["gold_in_tree"] == 1


def test_evaluate_with_diagnostics_external_l1_style_metadata_unchanged() -> None:
    from scripts.run_cohere_real_model_cost_normalized_validation import evaluate_with_diagnostics

    nodes = [{"branch_id": "l1_0", "predicted_answer": "8", "reasoning_text": "", "score": 0.5}]
    md = {
        "external_baseline_family": "l1_lcpo_length_control",
        "action_trace": [],
    }
    result = SimpleNamespace(metadata=md)
    diag = evaluate_with_diagnostics(result, "openai/gsm8k", "8", nodes, True)
    assert diag["exact_match"] == 1
    assert diag.get("final_answer_source") == "repair_layer"


def test_decide_pal_strong_overlay_blocks_peer_three_without_pal_mass() -> None:
    from experiments.output_layer_repair import decide_pal_strong_overlay_promotion

    promote, reason, diag = decide_pal_strong_overlay_promotion(
        combined_group_counts_base={"9": 3},
        pal_answer_raw="5",
        incumbent_final_answer_raw="9",
        frontier_weak=False,
        tiebreak_triggered=False,
        tiebreak_selected_group_raw="",
        strong_pal=True,
        pal_score=0.99,
    )
    assert promote is False
    assert "blocked" in reason
    assert diag.get("max_non_pal_histogram_support") == 3


def test_decide_pal_strong_overlay_allows_duplicate_wrong_twosome_when_histogram_two() -> None:
    from experiments.output_layer_repair import decide_pal_strong_overlay_promotion

    promote, reason, _diag = decide_pal_strong_overlay_promotion(
        combined_group_counts_base={"120": 2},
        pal_answer_raw="480",
        incumbent_final_answer_raw="120",
        frontier_weak=False,
        tiebreak_triggered=False,
        tiebreak_selected_group_raw="",
        strong_pal=True,
        pal_score=1.0,
    )
    assert promote is True
    assert "displaces" in reason


def test_pal_residual_integration_skips_weak_exec_or_bad_safety_parse() -> None:
    from scripts.run_cohere_real_model_cost_normalized_validation import evaluate_with_diagnostics

    md = {
        "final_answer": "9",
        "selected_group": "9",
        "answer_group_support_counts": {"120": 2},
        "frontier_support": 2,
        "frontier_tiebreak_triggered": False,
        "frontier_tiebreak_selected_group": "",
        "frontier_result": None,
        "pal_execution": {
            "pal_candidate_is_strong": 1,
            "pal_exec_ok": 0,
            "pal_parse_ok": 1,
            "pal_safety_ok": 1,
            "pal_score": 1.0,
            "pal_candidate_answer": "480",
        },
        "pal_overlay": {"pal_overlay_applied": False},
    }
    result = SimpleNamespace(metadata=md)
    merged = [{"branch_id": "x", "predicted_answer": "9", "reasoning_text": "", "score": 0.5}]
    diag = evaluate_with_diagnostics(
        result,
        "openai/gsm8k",
        "480",
        merged,
        True,
        enable_finalization_guard=False,
        enable_pal_residual_strong_integration_fix=True,
    )
    assert diag["exact_match"] == 0
    pit = diag.get("pal_integration") or {}
    assert not bool(pit.get("pal_integration_fix_triggered"))


def test_pal_residual_integration_promotes_strong_pal_when_duplicate_wrong_twosome_like_t5_case24() -> None:
    """Gold-free analogue of openai_gsm8k_24 cohort (two-branch wrong incumbent)."""
    from scripts.run_cohere_real_model_cost_normalized_validation import evaluate_with_diagnostics

    md = {
        "final_answer": "120",
        "selected_group": "120",
        "answer_group_support_counts": {"120": 2},
        "frontier_support": 2,
        "frontier_tiebreak_triggered": False,
        "frontier_tiebreak_selected_group": "",
        "frontier_result": None,
        "pal_execution": {
            "pal_candidate_is_strong": 1,
            "pal_exec_ok": 1,
            "pal_parse_ok": 1,
            "pal_safety_ok": 1,
            "pal_score": 1.0,
            "pal_candidate_answer": "480",
            "pal_execution_result": {"pal_answer_normalized": "480"},
        },
        "pal_overlay": {"pal_overlay_applied": False},
    }
    nodes: list[dict] = [{"branch_id": "r0", "predicted_answer": "120", "reasoning_text": "", "score": 0.5}]
    result = SimpleNamespace(metadata=md)

    diag0 = evaluate_with_diagnostics(
        result,
        "openai/gsm8k",
        "480",
        nodes,
        True,
        enable_finalization_guard=False,
        enable_pal_residual_strong_integration_fix=False,
    )
    diag1 = evaluate_with_diagnostics(
        result,
        "openai/gsm8k",
        "480",
        nodes,
        True,
        enable_finalization_guard=False,
        enable_pal_residual_strong_integration_fix=True,
    )
    assert diag0["exact_match"] == 0
    assert diag1["exact_match"] == 1
    pit = diag1.get("pal_integration") or {}
    assert pit.get("pal_integration_fix_triggered") is True
