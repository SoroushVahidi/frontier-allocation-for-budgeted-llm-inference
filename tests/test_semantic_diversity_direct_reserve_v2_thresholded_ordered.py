from __future__ import annotations

import random

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
