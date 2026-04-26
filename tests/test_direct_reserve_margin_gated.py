from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import DirectReserveGateRerankController, MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies


class _DummyScorer:
    def score_branch(self, branch) -> float:
        return 0.0

    def pick_best(self, branches):
        return branches[0] if branches else None


class _ControlledDirectReserve(DirectReserveGateRerankController):
    def __init__(self, attempts: list[str], frontier_answer: str | None) -> None:
        super().__init__(
            generator=SimulatedBranchGenerator(rng=random.Random(7), max_depth=3, finish_prob_base=0.2, answer_noise=0.1),
            scorer=_DummyScorer(),
            max_actions_per_problem=4,
            strict_controller_factory=lambda _remaining: MethodResult(
                method="stub",
                prediction=frontier_answer,
                is_correct=False,
                actions_used=0,
                expansions=0,
                verifications=0,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={},
            ),
            direct_prompt_styles=["style_a", "style_b"],
            direct_reserve_attempts_override=len(attempts),
            gate_top_support_threshold=2.0,
            gate_top2_gap_threshold=2.0,
            gate_entropy_threshold=-1.0,
            enable_margin_gate_fallback=True,
            margin_gate_min_support_gap=1,
            margin_gate_max_entropy=0.90,
            method_name="direct_reserve_strong_plus_diverse_margin_gated_v1",
        )
        self._attempts = attempts

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int):
        return self._attempts[idx], 1, []

    def run(self, question: str, gold_answer: str):
        # Adapt strict factory to controller return type.
        original = self.strict_controller_factory
        self.strict_controller_factory = lambda _remaining: type("S", (), {"run": lambda _self, _q, _g: original(0)})()
        return super().run(question, gold_answer)


def test_margin_gated_method_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(rng=random.Random(5), max_depth=4, finish_prob_base=0.2, answer_noise=0.1),
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=random.Random(6),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert "direct_reserve_strong_plus_diverse_margin_gated_v1" in specs


def test_gate_keeps_clear_majority_without_fallback() -> None:
    ctrl = _ControlledDirectReserve(attempts=["10", "10"], frontier_answer="10")
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert res.prediction == "10"
    assert meta["margin_gate_triggered"] is False
    assert meta["fallback_used"] is False


def test_gate_falls_back_on_tie_and_emits_metadata() -> None:
    ctrl = _ControlledDirectReserve(attempts=["10", "11"], frontier_answer="11")
    res = ctrl.run("q", "10")
    meta = dict(res.metadata or {})
    assert meta["margin_gate_triggered"] is True
    assert meta["fallback_used"] is True
    assert meta["fallback_source"] == "direct_reserve_primary"
    assert meta["selected_before_gate"] == "11"
    assert meta["selected_after_gate"] == "10"
    for key in [
        "support_margin",
        "answer_entropy",
        "num_answer_groups",
        "prompt_style_agreement",
        "gate_reason",
    ]:
        assert key in meta
