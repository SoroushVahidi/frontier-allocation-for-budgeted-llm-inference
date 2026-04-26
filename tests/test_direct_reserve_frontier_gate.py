from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import (
    DirectReserveFrontierGateController,
    DirectReserveFrontierGateV2Controller,
    GlobalDiversityAggregationController,
    MethodResult,
    NearDirectReserveFrontierGateController,
)
from experiments.frontier_matrix_core import build_frontier_strategies


class _DummyScorer:
    def score_branch(self, branch) -> float:
        return 0.0

    def pick_best(self, branches):
        return branches[0] if branches else None


class _ControlledReserveFrontierGate(DirectReserveFrontierGateController):
    def __init__(self, attempts: list[str], frontier_answer: str | None, frontier_support: dict[str, int]) -> None:
        def _mk_frontier(_remaining):
            result = MethodResult(
                method="stub_frontier",
                prediction=frontier_answer,
                is_correct=False,
                actions_used=1,
                expansions=1,
                verifications=1,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={"answer_group_support_counts": frontier_support},
            )
            return type("S", (), {"run": lambda _self, _q, _g: result})()

        super().__init__(
            generator=SimulatedBranchGenerator(rng=random.Random(17), max_depth=3, finish_prob_base=0.2, answer_noise=0.1),
            scorer=_DummyScorer(),
            max_actions_per_problem=5,
            strict_controller_factory=_mk_frontier,
            direct_prompt_styles=["style_a", "style_b"],
            direct_reserve_attempts_override=len(attempts),
            direct_token_budget=256,
            frontier_override_min_support_margin=1,
            frontier_override_min_maturity=2,
            method_name="direct_reserve_frontier_gate_v1",
        )
        self._attempts = attempts

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int):
        return self._attempts[idx], 1, []


class _ControlledReserveFrontierGateV2(DirectReserveFrontierGateV2Controller):
    def __init__(self, attempts: list[str], frontier_answer: str | None, frontier_support: dict[str, int]) -> None:
        def _mk_frontier(_remaining):
            result = MethodResult(
                method="stub_frontier",
                prediction=frontier_answer,
                is_correct=False,
                actions_used=1,
                expansions=1,
                verifications=1,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={"answer_group_support_counts": frontier_support},
            )
            return type("S", (), {"run": lambda _self, _q, _g: result})()

        super().__init__(
            generator=SimulatedBranchGenerator(rng=random.Random(19), max_depth=3, finish_prob_base=0.2, answer_noise=0.1),
            scorer=_DummyScorer(),
            max_actions_per_problem=5,
            strict_controller_factory=_mk_frontier,
            direct_prompt_styles=["style_a", "style_b"],
            direct_reserve_attempts_override=len(attempts),
            direct_token_budget=256,
            frontier_override_min_support_margin=1,
            frontier_override_min_maturity=2,
            method_name="direct_reserve_frontier_gate_v2",
        )
        self._attempts = attempts

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int):
        return self._attempts[idx], 1, []


class _ControlledNearDirectFrontierGate(NearDirectReserveFrontierGateController):
    def __init__(self, protected_answer: str, frontier_answer: str | None, frontier_support: dict[str, int]) -> None:
        def _mk_frontier(_remaining):
            result = MethodResult(
                method="stub_frontier",
                prediction=frontier_answer,
                is_correct=False,
                actions_used=1,
                expansions=1,
                verifications=1,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={"answer_group_support_counts": frontier_support},
            )
            return type("S", (), {"run": lambda _self, _q, _g: result})()

        super().__init__(
            generator=SimulatedBranchGenerator(rng=random.Random(23), max_depth=3, finish_prob_base=0.2, answer_noise=0.1),
            scorer=_DummyScorer(),
            max_actions_per_problem=5,
            strict_controller_factory=_mk_frontier,
            method_name="near_direct_reserve_frontier_gate_v1",
        )
        self._protected_answer = protected_answer

    def _run_protected_incumbent(self, question: str, gold_answer: str, max_actions: int):
        return self._protected_answer, 1, [], []


def test_reserve_kept_when_frontier_evidence_weak() -> None:
    ctrl = _ControlledReserveFrontierGate(attempts=["10", "10"], frontier_answer="11", frontier_support={"11": 1})
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert res.prediction == "10"
    assert meta["reserve_used"] is True
    assert meta["frontier_override_triggered"] is False
    assert meta["override_reason"] in {
        "single_weak_frontier_branch",
        "insufficient_support_margin",
        "frontier_not_run_or_budget_exhausted",
    }


def test_frontier_override_requires_margin_and_maturity() -> None:
    ctrl = _ControlledReserveFrontierGate(attempts=["10", "11"], frontier_answer="11", frontier_support={"11": 3, "10": 1})
    res = ctrl.run("q", "11")
    meta = dict(res.metadata or {})
    assert res.prediction == "11"
    assert meta["frontier_override_triggered"] is True
    assert meta["reserve_used"] is False
    assert float(meta["override_margin"]) >= 1.0


def test_v2_blocks_override_when_incumbent_seen_in_frontier_support() -> None:
    ctrl = _ControlledReserveFrontierGateV2(attempts=["10", "11"], frontier_answer="11", frontier_support={"11": 3, "10": 1})
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert res.prediction == "10"
    assert meta["frontier_override_triggered"] is False
    assert meta["reserve_used"] is True
    assert meta["incumbent_seen_in_frontier_support"] is True
    assert meta["v2_incumbent_support_guard_applied"] is True
    assert meta["v2_override_block_reason"] == "incumbent_seen_in_frontier_support"


def test_v2_allows_override_when_incumbent_absent_and_frontier_strong() -> None:
    ctrl = _ControlledReserveFrontierGateV2(attempts=["10", "12"], frontier_answer="11", frontier_support={"11": 3})
    res = ctrl.run("q", "11")
    meta = dict(res.metadata or {})
    assert res.prediction == "11"
    assert meta["frontier_override_triggered"] is True
    assert meta["reserve_used"] is False
    assert meta["incumbent_seen_in_frontier_support"] is False
    assert meta["v2_incumbent_support_guard_applied"] is False


def test_near_direct_returns_protected_incumbent_when_frontier_weak() -> None:
    ctrl = _ControlledNearDirectFrontierGate("10", "11", {"11": 1})
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert res.prediction == "10"
    assert meta["protected_incumbent_answer"] == "10"
    assert meta["frontier_override_triggered"] is False
    assert meta["override_block_reason"] == "single_weak_frontier_branch"


def test_near_direct_blocks_when_protected_incumbent_seen_in_frontier_support() -> None:
    ctrl = _ControlledNearDirectFrontierGate("10", "11", {"11": 3, "10": 1})
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert res.prediction == "10"
    assert meta["protected_incumbent_seen_in_frontier_support"] is True
    assert meta["incumbent_support_guard_applied"] is True
    assert meta["frontier_override_triggered"] is False
    assert meta["override_block_reason"] == "protected_incumbent_seen_in_frontier_support"


def test_near_direct_can_override_when_incumbent_absent_and_frontier_strong() -> None:
    ctrl = _ControlledNearDirectFrontierGate("10", "11", {"11": 3})
    res = ctrl.run("q", "11")
    meta = dict(res.metadata or {})
    assert res.prediction == "11"
    assert meta["frontier_override_triggered"] is True
    assert meta["protected_incumbent_seen_in_frontier_support"] is False
    assert meta["override_block_reason"] == "not_blocked"


def test_strict_f3_variant_registration_unchanged() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(rng=random.Random(5), max_depth=4, finish_prob_base=0.2, answer_noise=0.1),
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=random.Random(6),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert "strict_f3_anti_collapse_default_v1" in specs
    assert isinstance(specs["strict_f3_anti_collapse_default_v1"], GlobalDiversityAggregationController)
    assert "direct_reserve_frontier_gate_v1" in specs
    assert "direct_reserve_frontier_gate_v2" in specs
    assert "near_direct_reserve_frontier_gate_v1" in specs
