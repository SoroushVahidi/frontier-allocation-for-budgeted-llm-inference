"""Diagnostic-only semantic-diversity controllers (not canonical paper methods).

Keys are stable short names for scripts and logging. Does not modify strict_f3 / external_l1_max specs.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.controllers import (
    DirectReserveGateRerankController,
    DirectReserveGateRerankControllerV2,
    GlobalDiversityAggregationController,
)


def strict_f3_diagnostic_base_kwargs() -> dict[str, Any]:
    """Mirrors `strict_f3_base_cfg` in frontier_matrix_core (canonical strict_f3 hyperparameters)."""
    return dict(
        max_branches=4,
        min_branch_expansions=1,
        diversity_weight=0.40,
        duplicate_penalty=0.15,
        unknown_answer_bonus=0.08,
        answer_support_weight=0.55,
        value_weight=0.45,
        commit_support_threshold=0.72,
        commit_delay_min_actions=4,
        enable_early_answer_group_preservation=True,
        early_preservation_action_window=5,
        early_preservation_min_plausible_continuation=0.46,
        early_preservation_target_alignment_min=0.34,
        early_preservation_required_group_gap=0.18,
        early_preservation_challenger_hold_steps=2,
        enable_anti_collapse_answer_group_refinement=True,
        anti_collapse_early_window=6,
        repeated_same_branch_penalty=0.09,
        repeated_same_branch_cap=3,
        repeat_expand_free_steps=3,
        repeat_expand_penalty_weight=0.065,
        repeat_expand_family_penalty_weight=0.12,
        repeat_expand_override_margin=0.08,
        monopolization_margin_requirement=0.11,
        answer_group_distinctness_bonus=0.12,
        duplicate_answer_group_penalty=0.08,
        min_followup_steps_for_preserved_alternative=2,
        alternative_maturity_window=5,
        protected_alternative_target_alignment_min=0.48,
        enable_hard_early_root_depth2_coverage_v1=False,
        hard_early_root_coverage_forced_min_depth=3,
        hard_early_coverage_min_remaining_actions_to_release=0,
    )


def build_semantic_diversity_diagnostic_strategies(
    generator_factory: Callable[[], Any],
    scorer: Any,
    budget: int,
) -> dict[str, Any]:
    """Return experimental diagnostic controllers keyed by short method names."""
    base = strict_f3_diagnostic_base_kwargs()
    specs: dict[str, Any] = {}

    specs["semantic_minimum_maturation_frontier_v1_d2"] = GlobalDiversityAggregationController(
        generator_factory(),
        scorer,
        budget,
        method_name="semantic_minimum_maturation_frontier_v1_d2",
        **base,
        diagnostic_semantic_maturation=True,
        diagnostic_semantic_maturation_min_depth=2,
        diagnostic_log_semantic_families=True,
    )
    specs["semantic_minimum_maturation_frontier_v1_d3"] = GlobalDiversityAggregationController(
        generator_factory(),
        scorer,
        budget,
        method_name="semantic_minimum_maturation_frontier_v1_d3",
        **base,
        diagnostic_semantic_maturation=True,
        diagnostic_semantic_maturation_min_depth=3,
        diagnostic_log_semantic_families=True,
    )
    specs["branching_necessity_gate_v1"] = GlobalDiversityAggregationController(
        generator_factory(),
        scorer,
        budget,
        method_name="branching_necessity_gate_v1",
        **base,
        diagnostic_branching_necessity_heuristic=True,
        diagnostic_log_semantic_families=True,
    )

    def _strict_inner(remaining: int) -> GlobalDiversityAggregationController:
        return GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            remaining,
            method_name="strict_f3_inner_semantic_direct_reserve",
            **base,
        )

    specs["direct_reserve_semantic_frontier_v1"] = DirectReserveGateRerankController(
        generator_factory(),
        scorer,
        budget,
        strict_controller_factory=_strict_inner,
        method_name="direct_reserve_semantic_frontier_v1",
        diagnostic_challenger_resistance=True,
        gate_top_support_threshold=0.62,
        gate_top2_gap_threshold=0.25,
        gate_entropy_threshold=0.72,
    )
    specs["direct_reserve_semantic_frontier_v2"] = DirectReserveGateRerankControllerV2(
        generator_factory(),
        scorer,
        budget,
        strict_controller_factory=_strict_inner,
        method_name="direct_reserve_semantic_frontier_v2",
        gate_top_support_threshold=0.70,
        gate_top2_gap_threshold=0.35,
        gate_entropy_threshold=0.78,
        frontier_challenge_cap_small=1,
        frontier_challenge_cap_large=2,
    )

    def _strict_inner_mat(remaining: int) -> GlobalDiversityAggregationController:
        return GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            remaining,
            method_name="strict_f3_inner_semantic_maturation_plus_reserve",
            **base,
            diagnostic_semantic_maturation=True,
            diagnostic_semantic_maturation_min_depth=2,
            diagnostic_protected_incumbent_release=True,
            diagnostic_log_semantic_families=True,
        )

    specs["semantic_minimum_maturation_plus_direct_reserve_v1"] = DirectReserveGateRerankController(
        generator_factory(),
        scorer,
        budget,
        strict_controller_factory=_strict_inner_mat,
        method_name="semantic_minimum_maturation_plus_direct_reserve_v1",
        diagnostic_challenger_resistance=True,
        gate_top_support_threshold=0.62,
        gate_top2_gap_threshold=0.25,
        gate_entropy_threshold=0.72,
    )

    return specs


DIAGNOSTIC_NAMESPACE = "semantic_diversity_diagnostic_v1"
