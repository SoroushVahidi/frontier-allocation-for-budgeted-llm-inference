from __future__ import annotations

from typing import Any

from experiments.controllers import MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    DirectReserveDiverseRootFrontierV1GuardedController,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_STABILITY_REDUNDANT_ANCHOR,
)


class _Branch:
    def __init__(self, branch_id: str) -> None:
        self.branch_id = branch_id
        self.predicted_answer: str | None = None
        self.is_done = False
        self.is_pruned = False
        self.trace_events: list[dict[str, Any]] = []


class _MockGenerator:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.idx = 0

    def init_branch(self, branch_id: str) -> _Branch:
        return _Branch(branch_id)

    def expand(self, branch: _Branch, question: str, gold_answer: str) -> None:
        answer = self.answers[self.idx] if self.idx < len(self.answers) else self.answers[-1]
        self.idx += 1
        branch.predicted_answer = answer
        branch.is_done = True
        branch.trace_events.append(
            {
                "reasoning_text": f"Reasoned answer is {answer}",
                "extracted_answer": answer,
                "response_text": f"Reasoned answer is {answer}",
            }
        )


class _MockScorer:
    def score(self, branch: _Branch, question: str, gold_answer: str) -> float:
        return 1.0


class _MockFrontier:
    def __init__(self, answer: str, support: int = 2) -> None:
        self.answer = answer
        self.support = support

    def run(self, question: str, gold_answer: str) -> MethodResult:
        group = normalize_answer_group_key(self.answer)
        return MethodResult(
            method="mock_frontier",
            prediction=self.answer,
            is_correct=False,
            actions_used=1,
            expansions=1,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={
                "answer_group_support_counts": {group: int(self.support)},
                "frontier_candidate_answer": self.answer,
                "frontier_candidate_support": int(self.support),
            },
        )


def _controller(
    answers: list[str],
    *,
    frontier_answer: str = "24",
    frontier_support: int = 2,
    enable_guard: bool = False,
    enable_stability: bool = False,
    stability_domain_gate: str = "disabled",
    stability_attempts: int = 0,
    stability_target_anchor_id: str = "",
    enable_direct_hybrid_seed: bool = True,
    max_actions_per_problem: int = 7,
) -> DirectReserveDiverseRootFrontierV1GuardedController:
    return DirectReserveDiverseRootFrontierV1GuardedController(
        _MockGenerator(answers),
        _MockScorer(),
        max_actions_per_problem=max_actions_per_problem,
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=enable_direct_hybrid_seed,
        direct_hybrid_seed_budget_actions=1,
        enable_diverse_prompt_anchors=True,
        diverse_prompt_anchor_budget_actions=1,
        enable_diverse_anchor_regression_guard=enable_guard,
        enable_diverse_anchor_stability_policy=enable_stability,
        diverse_anchor_stability_policy="stability_redundant_anchor_v1" if enable_stability else "disabled",
        diverse_anchor_stability_domain_gate=stability_domain_gate,
        diverse_anchor_stability_extra_anchor_attempts=stability_attempts,
        diverse_anchor_stability_target_anchor_id=stability_target_anchor_id,
        enable_frontier_max_support_tiebreak=True,
        gate_top_support_threshold=2.0,
        strict_controller_factory=lambda _remaining_budget: _MockFrontier(frontier_answer, frontier_support),
    )


def test_regression_guard_disabled_by_default_reports_disabled_metadata() -> None:
    ctrl = _controller(
        ["20", "20", "24", "24", "24"],
        frontier_answer="24",
        frontier_support=2,
        enable_direct_hybrid_seed=False,
        max_actions_per_problem=7,
    )

    result = ctrl.run("A ratio/proportion/percentage problem.", "24")
    metadata = result.metadata

    assert metadata["regression_guard_available"] is True
    assert metadata["regression_guard_enabled"] is False
    assert metadata["regression_guard_triggered"] is False
    assert metadata["regression_guard_reason"] == "disabled"
    assert metadata["detected_problem_domain"] == "ratio_percent"
    assert metadata["diverse_prompt_anchor_ids_executed"] == [
        "direct_l1_anchor",
        "ratio_percentage_anchor",
        "equation_first_anchor",
        "unit_ledger_money_anchor",
        "backward_check_anchor",
    ]
    assert metadata["answer_group_support_counts"][normalize_answer_group_key("24")] >= 2


def test_regression_guard_can_be_enabled_for_direct_l1_domination() -> None:
    ctrl = _controller(
        ["24", "18", "80", "48", "20"],
        frontier_answer="24",
        frontier_support=2,
        enable_guard=True,
        max_actions_per_problem=6,
    )

    result = ctrl.run("A money/cost/revenue problem.", "24")
    metadata = result.metadata

    assert metadata["final_answer"] == "24"
    assert metadata["selected_group"] == "24"
    assert metadata["regression_guard_available"] is True
    assert metadata["regression_guard_enabled"] is True
    assert metadata["regression_guard_triggered"] is True
    assert metadata["regression_guard_reason"] == "preserve_frontier_budget_after_direct_l1_domination"
    assert metadata["anchor_dominant_selected_group"] == "18"
    assert metadata["direct_l1_anchor_dominant"] is True
    assert "24" in metadata["preserved_candidate_groups"]
    assert metadata["diverse_prompt_anchor_ids_executed"] == [
        "direct_l1_anchor",
        "unit_ledger_money_anchor",
        "equation_first_anchor",
        "ratio_percentage_anchor",
    ]
    assert any(
        row["skip_reason"] == "regression_guard_preserved_frontier_budget"
        for row in metadata["diverse_prompt_anchor_skipped"]
    )
    assert metadata["frontier_executed"] is True
    assert metadata["per_anchor_support"]["direct_l1_anchor"] == 1


def test_regression_guard_does_not_block_direct_l1_correct_improvement() -> None:
    ctrl = _controller(
        ["20", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=1,
        enable_guard=True,
        max_actions_per_problem=7,
    )

    result = ctrl.run("A money/cost/revenue problem.", "24")
    metadata = result.metadata

    assert metadata["final_answer"] == "24"
    assert metadata["selected_group"] == "24"
    assert metadata["regression_guard_available"] is True
    assert metadata["regression_guard_enabled"] is True
    assert metadata["regression_guard_triggered"] is False
    assert metadata["direct_l1_anchor_dominant"] is False
    assert metadata["diverse_prompt_anchor_ids_executed"][:3] == [
        "direct_l1_anchor",
        "unit_ledger_money_anchor",
        "equation_first_anchor",
    ]
    assert metadata["answer_group_support_counts"][normalize_answer_group_key("24")] >= 2


def test_regression_guard_does_not_block_domain_specific_anchor_improvement() -> None:
    ctrl = _controller(
        ["20", "20", "24", "24", "24"],
        frontier_answer="24",
        frontier_support=2,
        enable_guard=True,
        enable_direct_hybrid_seed=False,
        max_actions_per_problem=7,
    )

    result = ctrl.run("A ratio/proportion/percentage problem.", "24")
    metadata = result.metadata

    assert metadata["regression_guard_available"] is True
    assert metadata["regression_guard_enabled"] is True
    assert metadata["regression_guard_triggered"] is False
    assert metadata["detected_problem_domain"] == "ratio_percent"
    assert metadata["diverse_prompt_anchor_ids_executed"] == [
        "direct_l1_anchor",
        "ratio_percentage_anchor",
        "equation_first_anchor",
        "unit_ledger_money_anchor",
        "backward_check_anchor",
    ]
    assert metadata["selected_group"] == "20"
    assert metadata["answer_group_support_counts"][normalize_answer_group_key("24")] >= 2
    assert any(
        row["answer_group"] == "24"
        for row in metadata["diverse_prompt_anchor_metadata"]
        if row["anchor_id"] in {"ratio_percentage_anchor", "equation_first_anchor", "unit_ledger_money_anchor", "backward_check_anchor"}
    )


def test_stability_policy_disabled_by_default_reports_disabled_metadata() -> None:
    ctrl = _controller(
        ["20", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=2,
        max_actions_per_problem=7,
    )

    metadata = ctrl.run("A money/cost/revenue problem.", "24").metadata

    assert metadata["stability_policy"] == "disabled"
    assert metadata["stability_policy_enabled"] is False
    assert metadata["stability_domain_gate"] == "disabled"
    assert metadata["stability_domain_gate_allowed"] is False
    assert metadata["stability_extra_anchor_attempts"] == 0
    assert metadata["stability_target_anchor_id"] == ""
    assert metadata["stability_reason"] == "disabled"
    assert metadata["candidate_pool_stability_features"]["repeated_anchor_needed"] is False


def test_stability_policy_repeats_high_priority_anchor_when_enabled_for_multi_step() -> None:
    ctrl = _controller(
        ["20", "24", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=2,
        enable_stability=True,
        stability_domain_gate="multi_step_arithmetic_only_v1",
        stability_attempts=1,
        max_actions_per_problem=8,
    )

    metadata = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata

    assert metadata["stability_policy"] == "stability_redundant_anchor_v1"
    assert metadata["stability_policy_enabled"] is True
    assert metadata["stability_domain_gate"] == "multi_step_arithmetic_only_v1"
    assert metadata["stability_domain_gate_allowed"] is True
    assert metadata["stability_domain_gate_reason"] == "multi_step_arithmetic_allowed_by_default_gate"
    assert metadata["stability_extra_anchor_attempts"] == 1
    assert metadata["stability_target_anchor_id"] == "equation_first_anchor"
    assert metadata["stability_reason"] == "enabled_and_repeated"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("equation_first_anchor") == 2
    assert metadata["candidate_pool_stability_features"]["repeated_anchor_needed"] is True
    assert metadata["candidate_pool_stability_features"]["target_anchor_repeat_count"] == 2
    assert metadata["answer_group_support_counts"][normalize_answer_group_key("24")] >= 2


def test_stability_domain_gate_blocks_money_by_default() -> None:
    ctrl = _controller(
        ["20", "24", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=2,
        enable_stability=True,
        stability_domain_gate="multi_step_arithmetic_only_v1",
        stability_attempts=1,
        max_actions_per_problem=8,
    )

    metadata = ctrl.run("A money/cost/revenue problem.", "24").metadata

    assert metadata["detected_problem_domain"] == "money_cost_revenue"
    assert metadata["stability_policy_enabled"] is True
    assert metadata["stability_domain_gate"] == "multi_step_arithmetic_only_v1"
    assert metadata["stability_domain_gate_allowed"] is False
    assert metadata["stability_domain_gate_reason"] == "money_cost_revenue_blocked_by_default_gate"
    assert metadata["stability_target_anchor_id"] == ""
    assert metadata["stability_extra_anchor_attempts"] == 0
    assert metadata["stability_reason"] == "domain_gate_blocked"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("unit_ledger_money_anchor") == 1


def test_stability_domain_gate_blocks_ratio_by_default() -> None:
    ctrl = _controller(
        ["20", "24", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=2,
        enable_stability=True,
        stability_domain_gate="multi_step_arithmetic_only_v1",
        stability_attempts=1,
        max_actions_per_problem=8,
    )

    metadata = ctrl.run("A ratio/proportion/percentage problem.", "24").metadata

    assert metadata["detected_problem_domain"] == "ratio_percent"
    assert metadata["stability_policy_enabled"] is True
    assert metadata["stability_domain_gate"] == "multi_step_arithmetic_only_v1"
    assert metadata["stability_domain_gate_allowed"] is False
    assert metadata["stability_domain_gate_reason"] == "ratio_percent_blocked_by_default_gate"
    assert metadata["stability_target_anchor_id"] == ""
    assert metadata["stability_extra_anchor_attempts"] == 0
    assert metadata["stability_reason"] == "domain_gate_blocked"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("ratio_percentage_anchor") == 1


def test_stability_domain_gate_can_be_overridden_for_all_domains() -> None:
    ctrl = _controller(
        ["20", "24", "24", "24", "20", "20"],
        frontier_answer="24",
        frontier_support=2,
        enable_stability=True,
        stability_domain_gate="all_domains_v1",
        stability_attempts=1,
        max_actions_per_problem=8,
    )

    metadata = ctrl.run("A money/cost/revenue problem.", "24").metadata

    assert metadata["detected_problem_domain"] == "money_cost_revenue"
    assert metadata["stability_policy_enabled"] is True
    assert metadata["stability_domain_gate"] == "all_domains_v1"
    assert metadata["stability_domain_gate_allowed"] is True
    assert metadata["stability_domain_gate_reason"] == "override_all_domains"
    assert metadata["stability_target_anchor_id"] == "unit_ledger_money_anchor"
    assert metadata["stability_extra_anchor_attempts"] == 1
    assert metadata["stability_reason"] == "enabled_and_repeated"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("unit_ledger_money_anchor") == 2
    assert metadata["candidate_pool_stability_features"]["target_anchor_repeat_count"] == 2


def test_stability_policy_variant_is_registered_in_frontier_matrix() -> None:
    import random

    specs = build_frontier_strategies(
        generator_factory_for_mode(False, random.Random(7), "gpt-4o-mini", 0.1, 220, 30),
        8,
        [1],
        random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=False,
        include_external_s1_baseline=False,
        include_external_tale_baseline=False,
    )

    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_STABILITY_REDUNDANT_ANCHOR]
    assert getattr(ctrl, "enable_diverse_prompt_anchors", False) is True
    assert getattr(ctrl, "enable_diverse_anchor_stability_policy", False) is True
    assert getattr(ctrl, "diverse_anchor_stability_policy", "") == "stability_redundant_anchor_v1"
    assert getattr(ctrl, "diverse_anchor_stability_domain_gate", "") == "multi_step_arithmetic_only_v1"
    assert getattr(ctrl, "diverse_anchor_stability_extra_anchor_attempts", 0) == 1
