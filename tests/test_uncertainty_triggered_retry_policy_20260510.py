from __future__ import annotations

from typing import Any

from experiments.controllers import MethodResult
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    DirectReserveDiverseRootFrontierV1GuardedController,
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
                "answer_group_support_counts": {self.answer: int(self.support)},
                "frontier_candidate_answer": self.answer,
                "frontier_candidate_support": int(self.support),
            },
        )


def _controller(
    answers: list[str],
    *,
    question_budget: int = 8,
    enable_retry: bool = False,
    retry_policy: str = "uncertainty_triggered_retry_v1",
    retry_attempts: int = 1,
    direct_attempts_override: int = 2,
    enable_direct_hybrid_seed: bool = False,
    frontier_answer: str = "24",
    frontier_support: int = 2,
) -> DirectReserveDiverseRootFrontierV1GuardedController:
    return DirectReserveDiverseRootFrontierV1GuardedController(
        _MockGenerator(answers),
        _MockScorer(),
        max_actions_per_problem=question_budget,
        direct_reserve_attempts_override=direct_attempts_override,
        enable_direct_hybrid_seed=enable_direct_hybrid_seed,
        direct_hybrid_seed_budget_actions=1,
        enable_diverse_prompt_anchors=True,
        diverse_prompt_anchor_budget_actions=1,
        enable_diverse_anchor_uncertainty_retry_policy=enable_retry,
        diverse_anchor_uncertainty_retry_policy=retry_policy if enable_retry else "disabled",
        diverse_anchor_uncertainty_retry_extra_anchor_attempts=retry_attempts,
        enable_frontier_max_support_tiebreak=True,
        gate_top_support_threshold=2.0,
        strict_controller_factory=lambda _remaining_budget: _MockFrontier(frontier_answer, frontier_support),
    )


def _mixed_answers() -> list[str]:
    return ["20", "24", "20", "20", "20", "20", "20", "20"]


def test_uncertainty_retry_disabled_by_default_reports_disabled_metadata() -> None:
    ctrl = _controller(_mixed_answers(), enable_retry=False, question_budget=7)

    metadata = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata

    assert metadata["uncertainty_retry_policy"] == "disabled"
    assert metadata["uncertainty_retry_enabled"] is False
    assert metadata["uncertainty_retry_should_trigger"] is False
    assert metadata["uncertainty_retry_triggered"] is False
    assert metadata["uncertainty_retry_reason"] == "disabled"
    assert metadata["uncertainty_retry_target_anchor_id"] == ""
    assert metadata["uncertainty_retry_extra_attempts"] == 0
    assert metadata["diverse_prompt_anchor_ids_executed"][0] == "direct_l1_anchor"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("backward_check_anchor") == 1


def test_uncertainty_retry_triggers_for_multi_step_unstable_pool() -> None:
    ctrl = _controller(_mixed_answers(), enable_retry=True, question_budget=8)

    metadata = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata

    assert metadata["detected_problem_domain"] == "multi_step_arithmetic"
    assert metadata["uncertainty_retry_policy"] == "uncertainty_triggered_retry_v1"
    assert metadata["uncertainty_retry_enabled"] is True
    assert metadata["uncertainty_retry_should_trigger"] is True
    assert metadata["uncertainty_retry_triggered"] is True
    assert metadata["uncertainty_retry_reason"] == "enabled_and_retried"
    assert metadata["uncertainty_retry_target_anchor_id"] == "backward_check_anchor"
    assert metadata["uncertainty_retry_target_anchor_reason"] == "multi_step_arithmetic_preferred"
    assert metadata["uncertainty_retry_extra_attempts"] == 1
    assert metadata["uncertainty_retry_features"]["selected_group_is_weak"] is True
    assert metadata["uncertainty_retry_features"]["high_disagreement"] is True
    assert metadata["diverse_prompt_anchor_ids_executed"].count("backward_check_anchor") == 2


def test_uncertainty_retry_chooses_ratio_target_when_triggered() -> None:
    ctrl = _controller(_mixed_answers(), enable_retry=True, question_budget=8)

    metadata = ctrl.run("A ratio/proportion/percentage problem.", "24").metadata

    assert metadata["detected_problem_domain"] == "ratio_percent"
    assert metadata["uncertainty_retry_triggered"] is True
    assert metadata["uncertainty_retry_target_anchor_id"] == "ratio_percentage_anchor"
    assert metadata["uncertainty_retry_target_anchor_reason"] == "ratio_percent_preferred"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("ratio_percentage_anchor") == 2


def test_uncertainty_retry_chooses_money_target_when_triggered() -> None:
    ctrl = _controller(_mixed_answers(), enable_retry=True, question_budget=8)

    metadata = ctrl.run("A money/cost/revenue problem.", "24").metadata

    assert metadata["detected_problem_domain"] == "money_cost_revenue"
    assert metadata["uncertainty_retry_triggered"] is True
    assert metadata["uncertainty_retry_target_anchor_id"] == "unit_ledger_money_anchor"
    assert metadata["uncertainty_retry_target_anchor_reason"] == "money_cost_revenue_preferred"
    assert metadata["diverse_prompt_anchor_ids_executed"].count("unit_ledger_money_anchor") == 2


def test_uncertainty_retry_skips_when_no_budget_available() -> None:
    ctrl = _controller(_mixed_answers(), enable_retry=True, question_budget=7)

    metadata = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata

    assert metadata["uncertainty_retry_enabled"] is True
    assert metadata["uncertainty_retry_should_trigger"] is False
    assert metadata["uncertainty_retry_triggered"] is False
    assert metadata["uncertainty_retry_reason"] == "no_budget_available"
    assert metadata["uncertainty_retry_budget_available"] == 0
    assert metadata["uncertainty_retry_extra_attempts"] == 0


def test_uncertainty_retry_does_not_trigger_on_strong_consensus() -> None:
    ctrl = _controller(["20"] * 8, enable_retry=True, question_budget=8)

    metadata = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata

    assert metadata["uncertainty_retry_enabled"] is True
    assert metadata["uncertainty_retry_should_trigger"] is False
    assert metadata["uncertainty_retry_triggered"] is False
    assert metadata["uncertainty_retry_reason"] == "confidence_sufficient"
    assert metadata["uncertainty_retry_target_anchor_id"] == "backward_check_anchor"
    assert metadata["uncertainty_retry_extra_attempts"] == 0
