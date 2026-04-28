from __future__ import annotations

import random
from types import MethodType
from typing import Any

import pytest

from experiments.controllers import MethodResult
from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.semantic_diversity_diagnostic_strategies import (
    build_semantic_diversity_diagnostic_strategies,
    strict_f3_diagnostic_base_kwargs,
)


def _generator_factory() -> SimulatedBranchGenerator:
    return SimulatedBranchGenerator(rng=random.Random(991), max_depth=6, finish_prob_base=0.18, answer_noise=0.1)


def _diagnostic_specs(budget: int = 6) -> dict[str, object]:
    return build_semantic_diversity_diagnostic_strategies(
        generator_factory=_generator_factory,
        scorer=SimpleBranchScorer(ScoreConfig()),
        budget=budget,
    )


def test_v2_thresholded_ordered_registered() -> None:
    specs = _diagnostic_specs()
    assert "direct_reserve_semantic_frontier_v2_thresholded_ordered" in specs


def test_canonical_configs_unchanged() -> None:
    base = strict_f3_diagnostic_base_kwargs()
    assert base["max_branches"] == 4
    assert base["commit_support_threshold"] == 0.72
    assert base["hard_early_root_coverage_forced_min_depth"] == 3

    frontier = build_frontier_strategies(
        generator_factory=_generator_factory,
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=random.Random(77),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert "external_l1_max" in frontier
    assert "strict_f3_direct_reserve_gate_rerank_v1" in frontier


def test_v2_thresholded_ordered_smoke_logs_route_and_final_source() -> None:
    specs = _diagnostic_specs(budget=6)
    res = specs["direct_reserve_semantic_frontier_v2_thresholded_ordered"].run("What is 12+13?", "25")
    meta = dict(res.metadata or {})
    assert meta.get("route_decision") in {
        "stop_with_incumbent",
        "one_more_direct_continuation",
        "limited_frontier_challenge",
    }
    assert meta.get("final_source") in {"incumbent", "challenger"}


def test_v2_thresholded_ordered_handles_empty_direct_answers() -> None:
    specs = _diagnostic_specs(budget=6)
    ctrl = specs["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    ctrl._run_direct_attempt = lambda question, gold, idx, max_actions: (None, 0, [])
    res = ctrl.run("Compute 7 + 5", "12")
    meta = dict(res.metadata or {})
    assert "route_decision" in meta
    assert "final_source" in meta


def test_v2_thresholded_ordered_cap_lower_than_v1() -> None:
    specs = _diagnostic_specs(budget=8)
    v1 = specs["direct_reserve_semantic_frontier_v1"]
    v2 = specs["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    assert int(v2.frontier_challenge_cap_large) < int(v1.max_actions)


def _patch_direct_attempts(ctrl: Any, answers: list[str | None]) -> None:
    state = {"idx": 0}

    def _run_direct_attempt(self: Any, question: str, gold: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict[str, Any]]]:
        i = state["idx"]
        state["idx"] += 1
        answer = answers[i] if i < len(answers) else answers[-1]
        used = 0 if answer is None else min(1, max_actions)
        return answer, used, [{"attempt": i, "answer": answer}]

    ctrl._run_direct_attempt = MethodType(_run_direct_attempt, ctrl)


def _patch_frontier(ctrl: Any, challenger_answer: str | None, *, family_count: int = 2, challenger_family_support: int = 1) -> None:
    class _FrontierStub:
        def __init__(self, budget: int) -> None:
            self.budget = budget

        def run(self, question: str, gold_answer: str) -> MethodResult:
            sem_fams: dict[str, list[dict[str, Any]]] = {}
            if challenger_answer is not None:
                for i in range(max(family_count, challenger_family_support)):
                    group = challenger_answer if i < challenger_family_support else "other"
                    sem_fams[f"fam_{i}"] = [{"proxy_score": 0.6, "features": {"answer_group_bucket": group}}]
            return MethodResult(
                method="frontier_stub",
                prediction=challenger_answer,
                is_correct=str(challenger_answer or "").strip() == str(gold_answer).strip(),
                actions_used=self.budget,
                expansions=self.budget,
                verifications=0,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={"diagnostic_semantic_diversity": {"semantic_family_count": family_count, "family_redundancy_ratio": 0.7, "semantic_families": sem_fams}},
            )

    ctrl.strict_controller_factory = lambda budget: _FrontierStub(budget)


def test_strong_incumbent_stops_early_and_is_cheaper_than_v1() -> None:
    specs = _diagnostic_specs(budget=6)
    v1 = specs["direct_reserve_semantic_frontier_v1"]
    v2 = specs["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v1, ["25", "25"])
    _patch_direct_attempts(v2, ["25", "25"])
    _patch_frontier(v1, "26")
    _patch_frontier(v2, "26")

    v1_res = v1.run("What is 12+13?", "25")
    v2_res = v2.run("What is 12+13?", "25")
    m2 = dict(v2_res.metadata or {})
    assert m2["route_decision"] == "stop_with_incumbent"
    assert int(m2["frontier_opened"]) == 0
    assert int(m2["actions_used"]) < int(v1_res.actions_used)


def test_weak_or_empty_incumbent_opens_frontier() -> None:
    v2 = _diagnostic_specs(budget=6)["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v2, [None, None])
    _patch_frontier(v2, "12")
    res = v2.run("Compute 7 + 5", "12")
    meta = dict(res.metadata or {})
    assert meta["route_decision"] == "limited_frontier_challenge"
    assert int(meta["frontier_opened"]) == 1


def test_moderate_incumbent_can_take_one_more_direct_continuation() -> None:
    v2 = _diagnostic_specs(budget=6)["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v2, ["10", "10"])
    _patch_frontier(v2, "11")
    v2.commit_threshold = 0.95
    v2.gate_top2_gap_threshold = 1.1
    res = v2.run(
        "What is 5+5?",
        "10",
    )
    meta = dict(res.metadata or {})
    assert meta["route_decision"] == "one_more_direct_continuation"
    assert int(meta["frontier_opened"]) == 0
    assert int(meta["direct_actions_used"]) >= 3


def test_continuation_threshold_can_block_frontier_work() -> None:
    v2 = _diagnostic_specs(budget=8)["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v2, ["10", "20"])
    _patch_frontier(v2, "20")
    v2.continuation_threshold = 2.5
    res = v2.run("What is 10+10?", "20")
    meta = dict(res.metadata or {})
    assert meta["route_reason"] == "continuation_threshold_blocked_frontier"
    assert int(meta["frontier_opened"]) == 0
    assert float(meta["continuation_value_pre_frontier"]) < float(meta["continuation_threshold"])


def test_replacement_threshold_prevents_weak_challenger_replacement() -> None:
    v2 = _diagnostic_specs(budget=6)["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v2, ["25", "26"])
    _patch_frontier(v2, "26", family_count=1, challenger_family_support=1)
    v2.replacement_threshold = 0.0
    res = v2.run("What is 12+13?", "25")
    meta = dict(res.metadata or {})
    assert meta["final_source"] == "incumbent"


def test_strong_parseable_challenger_replaces_empty_incumbent() -> None:
    v2 = _diagnostic_specs(budget=6)["direct_reserve_semantic_frontier_v2_thresholded_ordered"]
    _patch_direct_attempts(v2, [None, None])
    _patch_frontier(v2, "12", family_count=2, challenger_family_support=2)
    res = v2.run("Compute 7 + 5", "12")
    meta = dict(res.metadata or {})
    assert meta["final_source"] == "challenger"
    for key in ["route_decision", "continuation_value", "final_source", "frontier_actions_used", "direct_actions_used"]:
        assert key in meta
