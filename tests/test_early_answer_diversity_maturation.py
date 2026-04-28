from __future__ import annotations

import random

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode


def _build_specs(budget: int = 6) -> dict[str, object]:
    rng = random.Random(17)
    return build_frontier_strategies(
        generator_factory=generator_factory_for_mode(
            use_openai_api=False,
            rng=rng,
            openai_model="command-r-plus-08-2024",
            temperature=0.1,
            max_output_tokens=256,
            timeout_seconds=45,
            api_provider="cohere",
        ),
        budget=budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def test_early_answer_diversity_maturation_registered() -> None:
    specs = _build_specs(budget=4)
    assert "early_answer_diversity_maturation_v1" in specs
    assert "early_answer_diversity_maturation_gated_v1" in specs


def test_early_answer_diversity_maturation_emits_prefix_metadata() -> None:
    specs = _build_specs(budget=6)
    controller = specs["early_answer_diversity_maturation_v1"]
    result = controller.run(
        "If a store sells 12 apples then sells 5 more and discards 4, how many remain?",
        "13",
    )
    meta = result.metadata
    assert bool(meta.get("early_answer_diversity_maturation_enabled", False))
    assert meta.get("early_answer_diversity_maturation_uses_gold_labels", True) is False
    assert int(meta.get("early_prefix", 0)) == min(3, max(1, 6 // 2))
    assert "early_maturation_actions" in meta
    assert "unique_answer_groups_seen_early" in meta
    assert "repeated_family_expansions_early" in meta
    assert "mature_groups_after_prefix" in meta
    assert "fallback_to_strict_f3_after_prefix" in meta
    trace = meta.get("action_trace") or []
    if trace:
        assert "early_answer_diversity_maturation_activated" in trace[0]
        assert "early_answer_diversity_maturation_reason" in trace[0]


def test_early_answer_diversity_maturation_gated_emits_metadata_and_no_gold_use() -> None:
    specs = _build_specs(budget=6)
    controller = specs["early_answer_diversity_maturation_gated_v1"]
    result = controller.run(
        "A warehouse has 40 boxes, receives 12, then ships 5. How many remain?",
        "47",
    )
    meta = result.metadata
    assert bool(meta.get("early_answer_diversity_maturation_gated_enabled", False))
    assert meta.get("early_answer_diversity_maturation_uses_gold_labels", True) is False
    assert "early_gated_override_considered" in meta
    assert "early_gated_override_applied" in meta
    assert "early_gated_override_triggers" in meta
    assert "early_gated_override_skipped_reason" in meta
    assert "unique_answer_groups_seen_early" in meta
    assert "repeated_family_expansions_early" in meta
    assert "mature_groups_after_prefix" in meta
    assert "fallback_to_strict_f3_after_prefix" in meta


def test_gated_no_collapse_case_matches_strict_or_no_override() -> None:
    specs = _build_specs(budget=4)
    gated = specs["early_answer_diversity_maturation_gated_v1"]
    b0 = gated.generator.init_branch("g0")
    b1 = gated.generator.init_branch("g1")
    b0.predicted_answer = "10"
    b1.predicted_answer = "11"
    scored = [
        (b0, 0.8, {"group_key": "10", "continuation_value": 0.8}),
        (b1, 0.7, {"group_key": "11", "continuation_value": 0.7}),
    ]
    selected, meta = gated._pick_early_answer_diversity_maturation_gated_branch(
        scored=scored,
        strict_branch=b0,
        strict_meta=scored[0][2],
        branches=[b0, b1],
        branch_family_ids={b0.branch_id: b0.branch_id, b1.branch_id: b1.branch_id},
        branch_expansions={},
        answer_support_counts={},
        actions=0,
        early_prefix=2,
        recent_groups=[],
        recent_families=[],
    )
    assert selected is None
    assert bool(meta.get("applied", False)) is False
    assert str(meta.get("skip_reason", "")) == "no_collapse_trigger"


def test_gated_records_override_in_collapse_trigger_case() -> None:
    specs = _build_specs(budget=8)
    gated = specs["early_answer_diversity_maturation_gated_v1"]
    questions = [
        ("A warehouse has 77 boxes, receives 16, then ships 21. How many remain?", "72"),
        ("A shelf has 63 books, 14 are added, then 19 are removed. How many remain?", "58"),
        ("A depot has 54 crates, gets 22 more, then sends out 17. How many remain?", "59"),
        ("A bin has 49 parts, adds 18, then discards 9. How many remain?", "58"),
    ]
    applied_any = False
    for q, g in questions:
        result = gated.run(q, g)
        if int(result.metadata.get("early_gated_override_applied", 0)) > 0:
            applied_any = True
            break
    assert applied_any
