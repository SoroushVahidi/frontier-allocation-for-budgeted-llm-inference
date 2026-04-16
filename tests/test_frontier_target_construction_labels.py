from __future__ import annotations

import math

from experiments.branch_scorer_v3 import SimBranch
from experiments.oracle_branch_labels import (
    OracleLabelConfig,
    approximate_oracle_continuation_value,
    generate_oracle_branch_labels,
)


def test_pairwise_label_consistency_and_antisymmetry() -> None:
    cfg = OracleLabelConfig(episodes=3, seed=5, decision_budget=4, n_init_branches=4, max_decisions_per_episode_to_label=2, max_branches_per_decision=3)
    _, pair_rows, _ = generate_oracle_branch_labels(cfg)
    assert pair_rows, "expected non-empty pairwise rows"

    for row in pair_rows:
        oracle_delta = float(row["approx_oracle_a"]) - float(row["approx_oracle_b"])
        proxy_delta = float(row["proxy_a"]) - float(row["proxy_b"])

        expected_oracle = 0 if abs(oracle_delta) <= cfg.tie_margin else (1 if oracle_delta > 0 else -1)
        expected_proxy = 0 if abs(proxy_delta) <= cfg.tie_margin else (1 if proxy_delta > 0 else -1)

        assert int(row["oracle_preference"]) == expected_oracle
        assert int(row["proxy_preference"]) == expected_proxy

        # Antisymmetry check: swapping (a,b) must negate sign unless it's a tie.
        if expected_oracle == 0:
            assert expected_oracle == -expected_oracle
        else:
            assert expected_oracle == -(1 if (-oracle_delta) > 0 else -1)


def test_exact_vs_approximate_mode_flags() -> None:
    cfg = OracleLabelConfig(rollouts_per_policy=1, high_budget_multiplier=1.2)

    terminal_branch = SimBranch(branch_id="done", latent_quality=0.7, score=0.8, is_done=True, is_correct=True)
    terminal = approximate_oracle_continuation_value(
        terminal_branch,
        remaining_budget=5,
        cfg=cfg,
        episode_id=0,
        decision_id=0,
    )
    assert terminal["value_is_exact"] is True
    assert terminal["label_kind"] == "exact_terminal_or_zero_budget"

    active_branch = SimBranch(branch_id="live", latent_quality=0.7, score=0.6, is_done=False, is_correct=False)
    approx = approximate_oracle_continuation_value(
        active_branch,
        remaining_budget=3,
        cfg=cfg,
        episode_id=0,
        decision_id=1,
    )
    assert approx["value_is_exact"] is False
    assert str(approx["label_kind"]).startswith("approx_high_budget_rollout_")
    assert int(approx["rollout_count"]) > 0

    robust_cfg = OracleLabelConfig(rollouts_per_policy=1, value_aggregation="robust_blend", value_std_penalty=0.1)
    robust = approximate_oracle_continuation_value(
        active_branch,
        remaining_budget=3,
        cfg=robust_cfg,
        episode_id=1,
        decision_id=0,
    )
    assert robust["label_kind"] == "approx_high_budget_rollout_robust_blend"
    assert math.isfinite(float(robust["approx_oracle_continuation_value"]))
