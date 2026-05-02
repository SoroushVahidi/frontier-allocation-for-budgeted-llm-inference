"""Smoke tests for direct_reserve_strategy_seeded_semantic_frontier_v2_final controller."""

from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import GlobalDiversityAggregationController
from experiments.data import PilotExample
from experiments.direct_reserve_strategy_seeded_semantic_frontier_v2_final import (
    DirectReserveStrategySeededSemanticFrontierV2FinalController,
    METHOD_DIRECT_RESERVE_STRATEGY_SEEDED_SEMANTIC_FRONTIER_V2_FINAL,
    prompt_digest,
    select_strategy_spec_indices,
)
from experiments.frontier_matrix_core import ScoreConfig, SimpleBranchScorer, build_frontier_strategies


def test_method_registered_in_frontier_specs() -> None:
    rng = random.Random(0)
    fac = lambda: SimulatedBranchGenerator(rng=rng, max_depth=3, finish_prob_base=0.2, answer_noise=0.08)
    specs = build_frontier_strategies(
        fac,
        8,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert "direct_reserve_strategy_seeded_semantic_frontier_v2_final" in specs
    ctl = specs["direct_reserve_strategy_seeded_semantic_frontier_v2_final"]
    assert isinstance(ctl, DirectReserveStrategySeededSemanticFrontierV2FinalController)


def test_prompt_digests_differ_across_strategy_families() -> None:
    q = "A store sells apples for $2."
    digs = []
    for idx in select_strategy_spec_indices(max_actions=10, question=q):
        from experiments.strategy_seeded_semantic_diversity_frontier_v1 import ROOT_STRATEGY_FAMILY_SPECS

        _, suf = ROOT_STRATEGY_FAMILY_SPECS[idx]
        body = f"{q}\n\n{suf} Think for maximum 640 tokens."
        digs.append(prompt_digest(body))
    assert len(set(digs)) == len(digs)


def test_simulated_controller_run_has_strategy_audit_without_gold_in_prompt_styles() -> None:
    rng = random.Random(3)
    fac = lambda: SimulatedBranchGenerator(rng=rng, max_depth=2, finish_prob_base=0.95, answer_noise=0.02)
    scorer = SimpleBranchScorer(ScoreConfig())
    kwargs = {
        "strict_controller_factory": lambda rb: GlobalDiversityAggregationController(
            fac(),
            scorer,
            rb,
            method_name="inner_smoke_strict_f3",
        ),
        "direct_prompt_style": "Explain briefly. Output \\boxed{}.",
        "direct_prompt_styles": [],
        "direct_token_budget": 128,
        "gate_top_support_threshold": 2.0,
        "gate_top2_gap_threshold": 2.0,
        "gate_entropy_threshold": -1.0,
    }
    ctl = DirectReserveStrategySeededSemanticFrontierV2FinalController(
        fac(),
        scorer,
        6,
        method_name=METHOD_DIRECT_RESERVE_STRATEGY_SEEDED_SEMANTIC_FRONTIER_V2_FINAL,
        strategy_seed_min_actions=1,
        min_actions_reserved_for_frontier=1,
        **kwargs,
    )
    ex = PilotExample(example_id="e0", question="What is 1+1?", answer="2")
    res = ctl.run(ex.question, ex.answer)
    assert res.metadata.get("strategy_seeded_v2_final_audit")
    dra = res.metadata.get("direct_reserve_attempts")
    assert isinstance(dra, list)
    digests = [str(x.get("prompt_digest", "")) for x in dra if isinstance(x, dict) and x.get("prompt_digest")]
    assert len(set(digests)) >= 1
    for row in dra:
        assert row.get("root_strategy_family") or row.get("prompt_digest")
        assert row.get("response_from_strategy_prompt") is True or row.get("action") == "expand"
