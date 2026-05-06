from __future__ import annotations

import argparse
import random

from experiments.frontier_matrix_core import build_frontier_strategies
from scripts.run_cohere_real_model_cost_normalized_validation import METHODS, validate_methods_only


def test_method_registry_includes_pal_tiebreak_id() -> None:
    mid = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
    assert mid in METHODS
    assert METHODS[mid]["runtime"] == mid


def test_validate_methods_only_pal_tiebreak_runnable(tmp_path) -> None:
    args = argparse.Namespace(
        timestamp="TEST_PAL_TIEBREAK_VALIDATE",
        output_root=str(tmp_path),
    )
    try:
        validate_methods_only(
            args=args,
            providers=["cohere"],
            budgets=[6],
            methods=["direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"],
        )
    except SystemExit as exc:
        assert exc.code == 0


def test_build_frontier_strategies_enables_real_pal_on_tiebreak_pal_controller() -> None:
    rng = random.Random(1)

    def factory():
        return None

    specs = build_frontier_strategies(
        factory,
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )

    ctl = specs["direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"]
    assert getattr(ctl, "enable_pal_branch", False) is True
    assert int(getattr(ctl, "pal_budget_actions", 0)) >= 1
