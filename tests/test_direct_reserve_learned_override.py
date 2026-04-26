from __future__ import annotations

import random
from typing import Any

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import BaseController, DirectReserveLearnedOverrideController, MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies
from scripts.direct_reserve_learned_override_utils import normalize_direct_reserve_plus_diverse_config


class _StubBasePlusDiverseController(BaseController):
    def __init__(self, prediction: str, candidates: list[dict[str, Any]]) -> None:
        super().__init__(generator=None, scorer=None, max_actions_per_problem=4)  # type: ignore[arg-type]
        self._prediction = prediction
        self._candidates = candidates

    def run(self, question: str, gold_answer: str) -> MethodResult:  # noqa: ARG002
        return MethodResult(
            method="direct_reserve_strong_plus_diverse_v1",
            prediction=self._prediction,
            is_correct=str(self._prediction) == str(gold_answer),
            actions_used=4,
            expansions=4,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={
                "final_selected_answer": self._prediction,
                "final_branch_states": list(self._candidates),
            },
        )


def _candidates() -> list[dict[str, Any]]:
    return [
        {"branch_id": "b0", "predicted_answer": "12", "group_key": "12", "selected": 1, "branch_depth": 1, "score": 1.0},
        {"branch_id": "b1", "predicted_answer": "9", "group_key": "9", "selected": 0, "branch_depth": 1, "score": 3.0},
    ]


def test_no_model_fallback_equals_base() -> None:
    base = _StubBasePlusDiverseController(prediction="12", candidates=_candidates())
    ctrl = DirectReserveLearnedOverrideController(base_controller=base, selector_fn=None)
    res = ctrl.run("q", "12")
    md = res.metadata
    assert md["learned_override_available"] is False
    assert md["learned_override_triggered"] is False
    assert md["final_selected_answer"] == md["base_selected_answer"] == "12"
    assert res.prediction == "12"


def test_high_threshold_no_override_equals_base() -> None:
    base = _StubBasePlusDiverseController(prediction="12", candidates=_candidates())

    def selector(rows: list[dict[str, Any]]) -> tuple[int | None, float, dict[str, float]]:
        return 1, 0.10, {"0": 0.0, "1": 0.1}

    ctrl = DirectReserveLearnedOverrideController(base_controller=base, selector_fn=selector, margin_threshold=999.0)
    res = ctrl.run("q", "12")
    md = res.metadata
    assert md["learned_override_triggered"] is False
    assert md["final_selected_answer"] == md["base_selected_answer"]
    assert res.prediction == "12"


def test_missing_feature_fallback_equals_base() -> None:
    base = _StubBasePlusDiverseController(prediction="12", candidates=_candidates())

    def selector(rows: list[dict[str, Any]]) -> tuple[int | None, float, dict[str, float]]:
        return 1, 100.0, {"0": 0.0, "1": 100.0}

    ctrl = DirectReserveLearnedOverrideController(
        base_controller=base,
        selector_fn=selector,
        required_feature_keys=["answer_group_support", "branch_depth", "missing_feature_key"],
    )
    res = ctrl.run("q", "12")
    md = res.metadata
    assert "missing_feature_key" in md["learned_override_missing_features"]
    assert md["learned_override_triggered"] is False
    assert md["final_selected_answer"] == md["base_selected_answer"] == "12"
    assert res.prediction == "12"


def test_valid_high_margin_override_changes_answer_only_when_triggered() -> None:
    base = _StubBasePlusDiverseController(prediction="12", candidates=_candidates())

    def selector(rows: list[dict[str, Any]]) -> tuple[int | None, float, dict[str, float]]:
        return 1, 10.0, {"0": 0.0, "1": 10.0}

    ctrl = DirectReserveLearnedOverrideController(base_controller=base, selector_fn=selector, margin_threshold=0.5)
    res = ctrl.run("q", "9")
    md = res.metadata
    assert md["learned_override_triggered"] is True
    assert md["base_selected_answer"] == "12"
    assert md["learned_selected_answer"] == "9"
    assert md["final_selected_answer"] == md["learned_selected_answer"] == "9"
    assert md["learned_override_reason"] == "margin_override"
    assert res.prediction == "9"


def test_method_registration_parity() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(123), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(456),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    base = specs["direct_reserve_strong_plus_diverse_v1"]
    learned = specs["direct_reserve_strong_plus_diverse_learned_override_v1"]
    assert normalize_direct_reserve_plus_diverse_config(base) == normalize_direct_reserve_plus_diverse_config(learned)

