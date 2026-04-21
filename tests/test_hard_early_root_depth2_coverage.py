"""Smoke tests for experimental hard early root depth-2 coverage refinement."""

from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples


def test_hard_early_coverage_methods_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(7), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=10,
        adaptive_min_expand_grid=[1],
        rng=random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
        in specs
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
        in specs
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1"
        in specs
    )


def test_hard_early_coverage_emits_metadata_fields() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=12,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert int(meta.get("hard_early_root_coverage_forced_min_depth") or 0) == 2
    assert meta.get("hard_early_root_depth2_coverage_v1_enabled") is True
    assert "hard_early_coverage_completed_fully" in meta
    assert "hard_early_coverage_final_family_status" in meta


def test_hard_early_depth3_coverage_emits_min_depth_metadata() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=12,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert int(meta.get("hard_early_root_coverage_forced_min_depth") or 0) == 3
    assert meta.get("hard_early_root_depth3_coverage_v1_enabled") is True


def test_conditional_depth3_gate_emits_metadata() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=14,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert meta.get("hard_early_root_depth2_then_conditional_depth3_v1_enabled") is True
    assert "conditional_depth3_gate_record" in meta
    assert "conditional_depth3_gate_thresholds" in meta
