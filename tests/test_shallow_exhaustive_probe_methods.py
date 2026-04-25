from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples


def test_exhaustive_probe_methods_are_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(13), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(17),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "strict_f3_exhaustive_depth2_probe" in specs
    assert "strict_f3_exhaustive_depth3_probe" in specs


def test_exhaustive_probe_emits_truncation_metadata_aliases() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    ex = load_pilot_examples("openai/gsm8k", 20, 11)[0]
    meta_d2 = specs["strict_f3_exhaustive_depth2_probe"].run(ex.question, ex.answer).metadata
    meta_d3 = specs["strict_f3_exhaustive_depth3_probe"].run(ex.question, ex.answer).metadata
    for meta in (meta_d2, meta_d3):
        assert "exhaustive_probe_budget_truncated" in meta
        assert "exhaustive_probe_planned_shallow_nodes_unexpanded" in meta
        assert "exhaustive_probe_transition_actions_used" in meta

