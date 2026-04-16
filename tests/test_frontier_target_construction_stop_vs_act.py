from __future__ import annotations

from experiments.stop_vs_act_controller import StopVsActLabelConfig, build_stop_vs_act_dataset


def test_branch_vs_outside_label_correctness() -> None:
    cfg = StopVsActLabelConfig(
        gain_margin=0.01,
        rollout_samples=3,
        target_mode="counterfactual_here_vs_best_other",
    )
    rows = build_stop_vs_act_dataset(
        episodes=4,
        budget=5,
        seed=19,
        train_ratio=0.75,
        n_init_branches=4,
        max_depth=6,
        finish_prob_base=0.16,
        answer_noise=0.12,
        label_cfg=cfg,
    )
    assert rows

    for row in rows:
        expected_label = int(float(row["delta_mean"]) > cfg.gain_margin)
        assert int(row["label_act"]) == expected_label
        # In this mode, comparator should be best-other expected gain.
        assert abs(float(row["stop_reference_gain"]) - float(row["best_other_gain"])) < 1e-9


def test_uncertainty_near_tie_rule_correctness() -> None:
    cfg = StopVsActLabelConfig(
        gain_margin=0.01,
        uncertainty_band=0.025,
        instability_std_threshold=0.04,
        instability_guard_band=0.03,
        rollout_samples=4,
        target_mode="proxy_best_other_gain",
    )
    rows = build_stop_vs_act_dataset(
        episodes=4,
        budget=5,
        seed=23,
        train_ratio=0.75,
        n_init_branches=4,
        max_depth=6,
        finish_prob_base=0.16,
        answer_noise=0.12,
        label_cfg=cfg,
    )
    assert rows

    saw_guard_filtered_case = False
    for row in rows:
        delta_mean = abs(float(row["delta_mean"]))
        delta_std = float(row["delta_std"])
        near_zero = delta_mean <= cfg.uncertainty_band
        unstable = delta_std >= cfg.instability_std_threshold
        instability_relevant = delta_mean <= float(cfg.instability_guard_band)
        expected_uncertain = near_zero or (unstable and instability_relevant)

        assert int(row["uncertain_near_zero"]) == int(near_zero)
        assert int(row["uncertain_unstable"]) == int(unstable)
        assert int(row["is_uncertain"]) == int(expected_uncertain)

        if unstable and (not instability_relevant):
            saw_guard_filtered_case = True
            assert int(row["is_uncertain"]) == int(near_zero)

    assert saw_guard_filtered_case, "expected at least one unstable-but-outside-guard example"
