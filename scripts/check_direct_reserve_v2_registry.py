#!/usr/bin/env python3
"""Small offline diagnostic checks for direct_reserve_semantic_frontier_v2."""

from __future__ import annotations

import random
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    build_semantic_diversity_diagnostic_registry,
    generator_factory_for_mode,
)
from experiments.scoring import ScoreConfig, SimpleBranchScorer

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def _build_specs(*, seed: int, budget: int) -> dict[str, object]:
    rng = random.Random(seed)
    factory = generator_factory_for_mode(
        use_openai_api=False,
        rng=rng,
        openai_model="command-r-plus-08-2024",
        temperature=0.2,
        max_output_tokens=512,
        timeout_seconds=60,
        api_provider=None,
    )
    base = build_frontier_strategies(
        generator_factory=factory,
        budget=budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    diag = build_semantic_diversity_diagnostic_registry(factory, SimpleBranchScorer(ScoreConfig()), budget)
    return {**base, **diag}


def main() -> int:
    question = "Mia has 3 bags with 4 marbles each. She buys 2 more marbles. How many marbles total?"
    gold = "14"

    # canonical methods stability sanity check
    s0 = _build_specs(seed=17, budget=6)
    s1 = _build_specs(seed=17, budget=6)
    strict0 = s0[STRICT_F3_RUNTIME].run(question, gold)
    strict1 = s1[STRICT_F3_RUNTIME].run(question, gold)
    ext0 = s0["external_l1_max"].run(question, gold)
    ext1 = s1["external_l1_max"].run(question, gold)
    assert strict0.prediction == strict1.prediction and strict0.actions_used == strict1.actions_used
    assert ext0.prediction == ext1.prediction and ext0.actions_used == ext1.actions_used

    specs = _build_specs(seed=23, budget=6)
    assert "direct_reserve_semantic_frontier_v2" in specs, "v2 missing from diagnostic registry"

    v1 = specs["direct_reserve_semantic_frontier_v1"].run(question, gold)
    v2 = specs["direct_reserve_semantic_frontier_v2"].run(question, gold)
    m2 = dict(v2.metadata or {})

    required = [
        "route_decision",
        "route_reason",
        "incumbent_parseable",
        "incumbent_confidence_proxy",
        "incumbent_kept_or_replaced",
        "frontier_opened",
        "frontier_actions_used",
        "direct_actions_used",
        "challenger_count",
        "final_source",
    ]
    missing = [k for k in required if k not in m2]
    assert not missing, f"v2 missing required metadata fields: {missing}"

    assert int(v2.actions_used) <= int(v1.actions_used), "v2 used more actions than v1 on sanity case"

    print("ok: direct_reserve_semantic_frontier_v2 registry+metadata sanity passed")
    print(f"v1_actions={v1.actions_used} v2_actions={v2.actions_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

