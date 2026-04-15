"""Lightweight stop-vs-act experimental path for fixed-budget allocation.

This module reuses the synthetic branch simulation primitives from
`experiments.branch_scorer_v3` and adds:
- bounded stop-vs-act label construction,
- uncertainty-aware filtering/reweighting helpers,
- lightweight model training and controller-level evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
from typing import Any, Literal

from experiments.branch_scorer_v3 import (
    SimBranch,
    _clip01,
    baseline_priority,
    branch_features_v6,
    expand_branch,
    expected_next_gain,
    maybe_verify,
)

STOP_VS_ACT_FEATURE_NAMES = [
    "remaining_budget",
    "score",
    "depth",
    "verify_count",
    "stalled_steps",
    "branch_age",
    "recent_delta",
    "score_entropy",
    "gap_to_best_other_score",
    "gap_to_best_other_gain",
    "best_other_gain",
    "expected_gain_here",
    "competition_tie_indicator",
    "parent_relative_score",
]


@dataclass
class StopVsActLabelConfig:
    gain_margin: float = 0.015
    uncertainty_band: float = 0.03
    instability_std_threshold: float = 0.045
    instability_guard_band: float | None = None
    rollout_samples: int = 6
    target_mode: Literal[
        "proxy_best_other_gain",
        "proxy_policy_coupled_stop_reallocation",
        "counterfactual_here_vs_best_other",
        "counterfactual_act_vs_stop_h2",
        "counterfactual_act_vs_stop_h2_matched",
    ] = "proxy_best_other_gain"
    small_horizon_steps: int = 2
    target_stabilization_mode: Literal["none", "repeated_local_averaging"] = "none"
    stabilization_repeats: int = 3


@dataclass
class StopVsActEvalArtifacts:
    metrics: dict[str, float]
    comparison_rows: list[dict[str, Any]]


def _safe_entropy(prob: float) -> float:
    p = _clip01(prob)
    if p <= 1e-8 or p >= 1 - 1e-8:
        return 0.0
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p))


def _snapshot_utility(branch: SimBranch) -> float:
    correctness = 1.0 if (branch.is_done and branch.is_correct) else 0.0
    done_bonus = 0.08 if branch.is_done else 0.0
    return 0.72 * float(branch.score) + 0.20 * correctness + done_bonus


def stop_vs_act_features(
    branch: SimBranch,
    active: list[SimBranch],
    *,
    remaining_budget: int,
    finish_prob_base: float,
    answer_noise: float,
) -> dict[str, float]:
    parent_mean_score = sum(b.score for b in active) / max(1, len(active))
    base = branch_features_v6(branch=branch, parent_mean_score=parent_mean_score, remaining_budget=remaining_budget)

    others = [b for b in active if b.branch_id != branch.branch_id]
    best_other_score = max((float(b.score) for b in others), default=float(branch.score))
    other_gains = [expected_next_gain(b, finish_prob_base, answer_noise) for b in others]
    best_other_gain = max(other_gains) if other_gains else expected_next_gain(branch, finish_prob_base, answer_noise)

    expected_gain_here = expected_next_gain(branch, finish_prob_base, answer_noise)
    score_entropy = _safe_entropy(float(branch.score))
    near_tie = abs(expected_gain_here - best_other_gain) <= 0.02

    features = {
        "remaining_budget": float(max(0, remaining_budget)),
        "score": float(branch.score),
        "depth": float(branch.depth),
        "verify_count": float(branch.verify_count),
        "stalled_steps": float(branch.stalled_steps),
        "branch_age": float(branch.branch_age),
        "recent_delta": float(branch.recent_delta),
        "score_entropy": score_entropy,
        "gap_to_best_other_score": float(branch.score) - best_other_score,
        "gap_to_best_other_gain": expected_gain_here - best_other_gain,
        "best_other_gain": best_other_gain,
        "expected_gain_here": expected_gain_here,
        "competition_tie_indicator": 1.0 if near_tie else 0.0,
        "parent_relative_score": float(base["parent_relative_score"]),
    }
    return features


def _clone_branch(branch: SimBranch) -> SimBranch:
    return SimBranch(
        branch_id=branch.branch_id,
        latent_quality=float(branch.latent_quality),
        score=float(branch.score),
        depth=int(branch.depth),
        is_done=bool(branch.is_done),
        is_pruned=bool(branch.is_pruned),
        is_correct=bool(branch.is_correct),
        stalled_steps=int(branch.stalled_steps),
        recent_delta=float(branch.recent_delta),
        verify_count=int(branch.verify_count),
        branch_age=int(branch.branch_age),
        action_history=list(branch.action_history),
        score_history=list(branch.score_history),
        depth_history=list(branch.depth_history),
    )


def _clone_active_branches(active: list[SimBranch]) -> list[SimBranch]:
    return [_clone_branch(b) for b in active]


def _stable_branch_seed_offset(branch_id: str) -> int:
    out = 0
    for i, ch in enumerate(branch_id):
        out += (i + 1) * ord(ch)
    return out


def _pick_best_active_for_local_rollout(active: list[SimBranch]) -> SimBranch:
    return max(active, key=lambda b: baseline_priority("adaptive_score_plus_progress", b, active))


def _local_rollout_value(
    *,
    active_snapshot: list[SimBranch],
    forced_first_branch_id: str | None,
    skip_first_branch_id: str | None,
    horizon_steps: int,
    rng: random.Random,
    finish_prob_base: float,
    answer_noise: float,
    max_depth: int,
) -> float:
    sim_active = _clone_active_branches(active_snapshot)
    horizon = max(1, int(horizon_steps))
    for step in range(horizon):
        live = [b for b in sim_active if not b.is_done and not b.is_pruned]
        if not live:
            break
        if step == 0 and forced_first_branch_id is not None:
            chosen = next((b for b in live if b.branch_id == forced_first_branch_id), None)
            if chosen is None:
                chosen = _pick_best_active_for_local_rollout(live)
        else:
            candidates = [b for b in live if b.branch_id != skip_first_branch_id] if (step == 0 and skip_first_branch_id) else live
            chosen = _pick_best_active_for_local_rollout(candidates or live)

        expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
        if not chosen.is_done and rng.random() < 0.35:
            maybe_verify(chosen, rng)

    return max((_snapshot_utility(b) for b in sim_active), default=0.0)


def estimate_act_gain_delta(
    branch: SimBranch,
    *,
    active: list[SimBranch],
    rng: random.Random,
    finish_prob_base: float,
    answer_noise: float,
    max_depth: int,
    rollout_samples: int,
    target_mode: Literal[
        "proxy_best_other_gain",
        "proxy_policy_coupled_stop_reallocation",
        "counterfactual_here_vs_best_other",
        "counterfactual_act_vs_stop_h2",
        "counterfactual_act_vs_stop_h2_matched",
    ] = "proxy_best_other_gain",
    small_horizon_steps: int = 2,
) -> tuple[float, float, float, float]:
    """Estimate local ACT delta for ACT-here versus a bounded local baseline.

    Returns:
        (delta_mean, delta_std, stop_reference, sign_flip_rate)

    target_mode:
        - proxy_best_other_gain: (legacy) uses best_other_expected_next_gain as stop reference.
        - proxy_policy_coupled_stop_reallocation: one-step local comparator with explicit
          policy-coupled STOP reallocation baseline. ACT forces action on this branch now;
          STOP forbids this branch at step 1 and reallocates that action using the same downstream policy.
        - counterfactual_here_vs_best_other: compares one simulated action here versus
          one simulated action on the best alternative branch from the same local snapshot.
        - counterfactual_act_vs_stop_h2: compare a short-horizon trajectory where step 1
          is forced ACT-here versus a matched short-horizon trajectory where step 1 skips
          this branch (STOP-here-now), then both continue with the same lightweight policy.
        - counterfactual_act_vs_stop_h2_matched: same as counterfactual_act_vs_stop_h2,
          but with paired common-random-number rollouts (same RNG seed per sample on ACT and STOP sides)
          to reduce nuisance randomness mismatch in the local ACT-vs-STOP comparator.
    """
    curr_utility = _snapshot_utility(branch)
    others = [b for b in active if b.branch_id != branch.branch_id]

    if target_mode == "proxy_best_other_gain":
        stop_reference = max((expected_next_gain(b, finish_prob_base, answer_noise) for b in others), default=0.0)
        deltas: list[float] = []
        for _ in range(max(1, rollout_samples)):
            sim = _clone_branch(branch)
            expand_branch(sim, rng, finish_prob_base, answer_noise, max_depth)
            if not sim.is_done and rng.random() < 0.35:
                maybe_verify(sim, rng)
            act_gain = _snapshot_utility(sim) - curr_utility
            deltas.append(act_gain - stop_reference)

        if not deltas:
            return 0.0, 0.0, stop_reference, 0.0
        mean_delta = sum(deltas) / len(deltas)
        var = sum((x - mean_delta) ** 2 for x in deltas) / max(1, len(deltas))
        std = math.sqrt(max(0.0, var))
        sign_flip_rate = float(sum(1 for x in deltas if x * mean_delta < 0.0) / max(1, len(deltas)))
        return mean_delta, std, stop_reference, sign_flip_rate

    if target_mode == "proxy_policy_coupled_stop_reallocation":
        stop_reference = max((expected_next_gain(b, finish_prob_base, answer_noise) for b in others), default=0.0)
        start_value = max((_snapshot_utility(b) for b in active), default=0.0)
        deltas = []
        stop_values = []
        for _ in range(max(1, rollout_samples)):
            paired_seed = rng.randint(0, 2**31 - 1)
            act_rng = random.Random(paired_seed)
            stop_rng = random.Random(paired_seed)
            act_value = _local_rollout_value(
                active_snapshot=active,
                forced_first_branch_id=branch.branch_id,
                skip_first_branch_id=None,
                horizon_steps=1,
                rng=act_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=max_depth,
            )
            stop_value = _local_rollout_value(
                active_snapshot=active,
                forced_first_branch_id=None,
                skip_first_branch_id=branch.branch_id,
                horizon_steps=1,
                rng=stop_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=max_depth,
            )
            deltas.append((act_value - start_value) - (stop_value - start_value))
            stop_values.append(stop_value - start_value)

        mean_delta = sum(deltas) / max(1, len(deltas))
        var = sum((x - mean_delta) ** 2 for x in deltas) / max(1, len(deltas))
        std = math.sqrt(max(0.0, var))
        sign_flip_rate = float(sum(1 for x in deltas if x * mean_delta < 0.0) / max(1, len(deltas)))
        policy_coupled_stop_ref = sum(stop_values) / max(1, len(stop_values))
        return mean_delta, std, policy_coupled_stop_ref, sign_flip_rate

    if target_mode in {"counterfactual_act_vs_stop_h2", "counterfactual_act_vs_stop_h2_matched"}:
        stop_reference = max((_snapshot_utility(b) for b in active), default=0.0)
        deltas = []
        for _ in range(max(1, rollout_samples)):
            paired_seed = rng.randint(0, 2**31 - 1)
            act_rng = random.Random(paired_seed) if target_mode == "counterfactual_act_vs_stop_h2_matched" else rng
            stop_rng = random.Random(paired_seed) if target_mode == "counterfactual_act_vs_stop_h2_matched" else rng
            act_value = _local_rollout_value(
                active_snapshot=active,
                forced_first_branch_id=branch.branch_id,
                skip_first_branch_id=None,
                horizon_steps=small_horizon_steps,
                rng=act_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=max_depth,
            )
            stop_value = _local_rollout_value(
                active_snapshot=active,
                forced_first_branch_id=None,
                skip_first_branch_id=branch.branch_id,
                horizon_steps=small_horizon_steps,
                rng=stop_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=max_depth,
            )
            deltas.append(act_value - stop_value)

        mean_delta = sum(deltas) / max(1, len(deltas))
        var = sum((x - mean_delta) ** 2 for x in deltas) / max(1, len(deltas))
        std = math.sqrt(max(0.0, var))
        sign_flip_rate = float(sum(1 for x in deltas if x * mean_delta < 0.0) / max(1, len(deltas)))
        return mean_delta, std, stop_reference, sign_flip_rate

    if target_mode != "counterfactual_here_vs_best_other":
        raise ValueError(f"Unsupported target_mode: {target_mode}")

    best_other = max(
        others,
        key=lambda b: expected_next_gain(b, finish_prob_base, answer_noise),
        default=branch,
    )
    stop_reference = expected_next_gain(best_other, finish_prob_base, answer_noise)

    deltas = []
    for _ in range(max(1, rollout_samples)):
        sim_here = _clone_branch(branch)
        sim_other = _clone_branch(best_other)

        expand_branch(sim_here, rng, finish_prob_base, answer_noise, max_depth)
        if not sim_here.is_done and rng.random() < 0.35:
            maybe_verify(sim_here, rng)

        expand_branch(sim_other, rng, finish_prob_base, answer_noise, max_depth)
        if not sim_other.is_done and rng.random() < 0.35:
            maybe_verify(sim_other, rng)

        here_gain = _snapshot_utility(sim_here) - curr_utility
        other_gain = _snapshot_utility(sim_other) - _snapshot_utility(best_other)
        deltas.append(here_gain - other_gain)

    if not deltas:
        return 0.0, 0.0, stop_reference, 0.0
    mean_delta = sum(deltas) / len(deltas)
    var = sum((x - mean_delta) ** 2 for x in deltas) / max(1, len(deltas))
    std = math.sqrt(max(0.0, var))
    sign_flip_rate = float(sum(1 for x in deltas if x * mean_delta < 0.0) / max(1, len(deltas)))
    return mean_delta, std, stop_reference, sign_flip_rate


def build_stop_vs_act_dataset(
    *,
    episodes: int,
    budget: int,
    seed: int,
    train_ratio: float,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    label_cfg: StopVsActLabelConfig,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []

    for episode_id in range(episodes):
        branches = [
            SimBranch(
                branch_id=f"b_{idx}",
                latent_quality=rng.uniform(0.2, 0.95),
                score=rng.uniform(0.25, 0.75),
            )
            for idx in range(n_init_branches)
        ]

        for decision_id in range(budget):
            for branch in branches:
                branch.branch_age += 1
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) <= 1:
                if not active:
                    break
                chosen = active[0]
                expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
                continue

            remaining = max(0, budget - decision_id)
            for branch in active:
                features = stop_vs_act_features(
                    branch,
                    active,
                    remaining_budget=remaining,
                    finish_prob_base=finish_prob_base,
                    answer_noise=answer_noise,
                )
                base_local_seed = (
                    (seed + 17) * 10_000_019
                    + episode_id * 104_729
                    + decision_id * 1009
                    + _stable_branch_seed_offset(branch.branch_id) * 97
                )

                if label_cfg.target_stabilization_mode == "none":
                    local_rng = random.Random(base_local_seed)
                    delta_mean, delta_std, stop_ref, delta_sign_flip_rate = estimate_act_gain_delta(
                        branch,
                        active=active,
                        rng=local_rng,
                        finish_prob_base=finish_prob_base,
                        answer_noise=answer_noise,
                        max_depth=max_depth,
                        rollout_samples=label_cfg.rollout_samples,
                        target_mode=label_cfg.target_mode,
                        small_horizon_steps=label_cfg.small_horizon_steps,
                    )
                    delta_repeat_std = 0.0
                    delta_within_std_mean = delta_std
                    delta_estimator_std = delta_std
                elif label_cfg.target_stabilization_mode == "repeated_local_averaging":
                    repeats = max(2, int(label_cfg.stabilization_repeats))
                    repeat_delta_means: list[float] = []
                    repeat_delta_stds: list[float] = []
                    stop_refs: list[float] = []
                    sign_flip_rates: list[float] = []
                    for ridx in range(repeats):
                        local_rng = random.Random(base_local_seed + ridx * 1_000_003)
                        d_mean, d_std, s_ref, s_flip = estimate_act_gain_delta(
                            branch,
                            active=active,
                            rng=local_rng,
                            finish_prob_base=finish_prob_base,
                            answer_noise=answer_noise,
                            max_depth=max_depth,
                            rollout_samples=label_cfg.rollout_samples,
                            target_mode=label_cfg.target_mode,
                            small_horizon_steps=label_cfg.small_horizon_steps,
                        )
                        repeat_delta_means.append(float(d_mean))
                        repeat_delta_stds.append(float(d_std))
                        stop_refs.append(float(s_ref))
                        sign_flip_rates.append(float(s_flip))

                    delta_mean = sum(repeat_delta_means) / max(1, len(repeat_delta_means))
                    stop_ref = sum(stop_refs) / max(1, len(stop_refs))
                    between_var = (
                        sum((x - delta_mean) ** 2 for x in repeat_delta_means) / max(1, len(repeat_delta_means))
                    )
                    delta_repeat_std = math.sqrt(max(0.0, between_var))
                    delta_within_std_mean = sum(repeat_delta_stds) / max(1, len(repeat_delta_stds))
                    within_var = sum((x**2) for x in repeat_delta_stds) / max(1, len(repeat_delta_stds))
                    estimator_var = (within_var + between_var) / float(repeats)
                    delta_estimator_std = math.sqrt(max(0.0, estimator_var))
                    delta_std = delta_estimator_std
                    delta_sign_flip_rate = sum(sign_flip_rates) / max(1, len(sign_flip_rates))
                else:
                    raise ValueError(f"Unsupported target_stabilization_mode: {label_cfg.target_stabilization_mode}")

                label_act = int(delta_mean > label_cfg.gain_margin)
                near_zero = abs(delta_mean) <= label_cfg.uncertainty_band
                unstable = delta_std >= label_cfg.instability_std_threshold
                instability_relevant = True
                if label_cfg.instability_guard_band is not None:
                    instability_relevant = abs(delta_mean) <= float(label_cfg.instability_guard_band)
                uncertain = bool(near_zero or (unstable and instability_relevant))

                weight = 1.0
                if uncertain:
                    if near_zero and unstable:
                        weight = 0.20
                    elif near_zero:
                        weight = 0.35
                    else:
                        weight = 0.50

                row: dict[str, Any] = {
                    "episode_id": episode_id,
                    "decision_id": decision_id,
                    "branch_id": branch.branch_id,
                    "split": "train" if episode_id < int(episodes * train_ratio) else "test",
                    "label_act": label_act,
                    "delta_mean": delta_mean,
                    "delta_std": delta_std,
                    "delta_repeat_std": delta_repeat_std,
                    "delta_within_std_mean": delta_within_std_mean,
                    "delta_estimator_std": delta_estimator_std,
                    "target_variance": delta_estimator_std * delta_estimator_std,
                    "target_reliability_weight": 1.0 / (1.0 + max(0.0, delta_estimator_std)),
                    "delta_sign_flip_rate": delta_sign_flip_rate,
                    "stop_reference_gain": stop_ref,
                    "is_uncertain": int(uncertain),
                    "sample_weight": weight,
                    "uncertain_near_zero": int(near_zero),
                    "uncertain_unstable": int(unstable),
                }
                row.update(features)
                rows.append(row)

            chosen = rng.choice(active)
            expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
            if not chosen.is_done and rng.random() < 0.35:
                maybe_verify(chosen, rng)

    return rows


def fit_stop_vs_act_model(
    train_rows: list[dict[str, Any]],
    *,
    model_kind: str,
    uncertain_policy: str,
    seed: int,
    reliability_power: float = 0.0,
) -> dict[str, Any]:
    import numpy as np  # type: ignore
    from sklearn.ensemble import GradientBoostingClassifier  # type: ignore
    from sklearn.linear_model import LogisticRegression  # type: ignore

    if uncertain_policy not in {"none", "filter", "downweight", "downweight_nonpositive"}:
        raise ValueError(f"Unsupported uncertain_policy: {uncertain_policy}")

    used = train_rows
    if uncertain_policy == "filter":
        used = [r for r in train_rows if not bool(r.get("is_uncertain", 0))]

    x = np.array([[float(r[name]) for name in STOP_VS_ACT_FEATURE_NAMES] for r in used])
    y = np.array([int(r["label_act"]) for r in used])
    weights = None
    if uncertain_policy == "downweight":
        weights = np.array([float(r.get("sample_weight", 1.0)) for r in used])
    elif uncertain_policy == "downweight_nonpositive":
        weights = np.array(
            [
                float(r.get("sample_weight", 1.0))
                if (bool(r.get("is_uncertain", 0)) and int(r.get("label_act", 0)) == 0)
                else 1.0
                for r in used
            ]
        )
    if reliability_power > 0.0:
        reliability = np.array(
            [max(0.0, min(1.0, float(r.get("target_reliability_weight", 1.0)))) ** reliability_power for r in used]
        )
        if weights is None:
            weights = reliability
        else:
            weights = weights * reliability

    if model_kind == "logistic":
        model = LogisticRegression(max_iter=1200, class_weight="balanced", random_state=seed)
        model.fit(x, y, sample_weight=weights)
        return {
            "model_type": "logistic",
            "feature_family": "stop_vs_act_v1",
            "feature_names": STOP_VS_ACT_FEATURE_NAMES,
            "uncertain_policy": uncertain_policy,
            "reliability_power": reliability_power,
            "weights": {name: float(w) for name, w in zip(STOP_VS_ACT_FEATURE_NAMES, model.coef_[0])},
            "intercept": float(model.intercept_[0]),
            "train_rows_used": len(used),
        }

    if model_kind == "gbdt":
        model = GradientBoostingClassifier(random_state=seed, n_estimators=120, max_depth=2)
        model.fit(x, y, sample_weight=weights)
        return {
            "model_type": "gbdt",
            "feature_family": "stop_vs_act_v1",
            "feature_names": STOP_VS_ACT_FEATURE_NAMES,
            "uncertain_policy": uncertain_policy,
            "reliability_power": reliability_power,
            "estimator": model,
            "train_rows_used": len(used),
        }

    raise ValueError(f"Unsupported model_kind: {model_kind}")


def stop_vs_act_probability(model: dict[str, Any], features: dict[str, float]) -> float:
    kind = str(model.get("model_type"))
    if kind == "logistic":
        linear = float(model.get("intercept", 0.0))
        for name, weight in model.get("weights", {}).items():
            linear += float(weight) * float(features.get(name, 0.0))
        if linear >= 0:
            return 1.0 / (1.0 + math.exp(-linear))
        exp_linear = math.exp(linear)
        return exp_linear / (1.0 + exp_linear)

    if kind == "gbdt":
        est = model.get("estimator")
        if est is None:
            raise ValueError("GBDT estimator missing")
        import numpy as np  # type: ignore

        x = np.array([[float(features[name]) for name in STOP_VS_ACT_FEATURE_NAMES]])
        return float(est.predict_proba(x)[0][1])

    raise ValueError(f"Unknown model_type: {kind}")


def evaluate_binary_predictions(
    model: dict[str, Any],
    test_rows: list[dict[str, Any]],
    *,
    threshold: float,
) -> dict[str, float]:
    scored: list[tuple[float, int, int]] = []
    for row in test_rows:
        features = {name: float(row[name]) for name in STOP_VS_ACT_FEATURE_NAMES}
        p = stop_vs_act_probability(model, features)
        y = int(row["label_act"])
        pred = 1 if p >= threshold else 0
        scored.append((p, y, pred))

    n = max(1, len(scored))
    tp = sum(1 for _, y, pred in scored if y == 1 and pred == 1)
    fp = sum(1 for _, y, pred in scored if y == 0 and pred == 1)
    tn = sum(1 for _, y, pred in scored if y == 0 and pred == 0)
    fn = sum(1 for _, y, pred in scored if y == 1 and pred == 0)
    acc = (tp + tn) / n
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    brier = sum((p - y) ** 2 for p, y, _ in scored) / n

    # Mann-Whitney view of ROC-AUC (rank based, no sklearn dependency).
    pos = [p for p, y, _ in scored if y == 1]
    neg = [p for p, y, _ in scored if y == 0]
    if pos and neg:
        wins = 0.0
        total = 0.0
        for p_pos in pos:
            for p_neg in neg:
                total += 1.0
                if p_pos > p_neg:
                    wins += 1.0
                elif p_pos == p_neg:
                    wins += 0.5
        auc = wins / max(1.0, total)
    else:
        auc = 0.5

    return {
        "rows": float(len(scored)),
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "brier": brier,
        "roc_auc": auc,
    }


def _pick_primary_candidate(active: list[SimBranch]) -> SimBranch:
    return max(active, key=lambda b: b.score)


def _pick_alternative_branch(active: list[SimBranch], excluded_id: str) -> SimBranch:
    alternatives = [b for b in active if b.branch_id != excluded_id]
    if not alternatives:
        return next(b for b in active if b.branch_id == excluded_id)
    return max(alternatives, key=lambda b: baseline_priority("adaptive_score_plus_progress", b, active))


def simulate_stop_vs_act_controller(
    *,
    policy_name: str,
    rng: random.Random,
    budget: int,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    model: dict[str, Any] | None,
    model_threshold: float,
    heuristic_margin: float,
    entropy_threshold: float,
) -> dict[str, Any]:
    branches = [
        SimBranch(
            branch_id=f"b_{idx}",
            latent_quality=rng.uniform(0.2, 0.95),
            score=rng.uniform(0.25, 0.75),
        )
        for idx in range(n_init_branches)
    ]

    act_on_primary = 0
    routed_elsewhere = 0

    for step in range(budget):
        for branch in branches:
            branch.branch_age += 1
        active = [b for b in branches if not b.is_done and not b.is_pruned]
        if not active:
            break

        primary = _pick_primary_candidate(active)
        features = stop_vs_act_features(
            primary,
            active,
            remaining_budget=budget - step,
            finish_prob_base=finish_prob_base,
            answer_noise=answer_noise,
        )

        if policy_name == "learned_stop_vs_act":
            if model is None:
                raise ValueError("learned policy requires model")
            act_here = stop_vs_act_probability(model, features) >= model_threshold
        elif policy_name == "heuristic_gain_gap":
            act_here = float(features["gap_to_best_other_gain"]) > heuristic_margin
        elif policy_name == "uncertainty_entropy_only":
            act_here = float(features["score_entropy"]) >= entropy_threshold
        else:
            raise ValueError(f"Unknown policy_name: {policy_name}")

        target = primary if act_here else _pick_alternative_branch(active, excluded_id=primary.branch_id)
        if target.branch_id == primary.branch_id:
            act_on_primary += 1
        else:
            routed_elsewhere += 1

        expand_branch(target, rng, finish_prob_base, answer_noise, max_depth)
        if not target.is_done and rng.random() < 0.35:
            maybe_verify(target, rng)

    done = [b for b in branches if b.is_done]
    best = max(done, key=lambda b: b.score) if done else max(branches, key=lambda b: b.score)

    return {
        "is_correct": bool(best.is_correct),
        "solved_any": any(b.is_correct for b in branches if b.is_done),
        "actions_used": budget,
        "avg_best_score": max(float(b.score) for b in branches),
        "act_on_primary": act_on_primary,
        "routed_elsewhere": routed_elsewhere,
    }


def evaluate_controller_comparison(
    *,
    model: dict[str, Any],
    seed: int,
    episodes: int,
    budget: int,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    model_threshold: float,
    heuristic_margin: float,
    entropy_threshold: float,
) -> StopVsActEvalArtifacts:
    rng = random.Random(seed)
    policy_names = ["learned_stop_vs_act", "heuristic_gain_gap", "uncertainty_entropy_only"]
    rows: list[dict[str, Any]] = []

    for policy in policy_names:
        metrics = []
        for _ in range(episodes):
            metrics.append(
                simulate_stop_vs_act_controller(
                    policy_name=policy,
                    rng=rng,
                    budget=budget,
                    n_init_branches=n_init_branches,
                    max_depth=max_depth,
                    finish_prob_base=finish_prob_base,
                    answer_noise=answer_noise,
                    model=model if policy == "learned_stop_vs_act" else None,
                    model_threshold=model_threshold,
                    heuristic_margin=heuristic_margin,
                    entropy_threshold=entropy_threshold,
                )
            )

        n = max(1, len(metrics))
        rows.append(
            {
                "policy": policy,
                "accuracy": sum(1 for m in metrics if m["is_correct"]) / n,
                "solve_rate": sum(1 for m in metrics if m["solved_any"]) / n,
                "avg_actions": sum(float(m["actions_used"]) for m in metrics) / n,
                "avg_best_score": sum(float(m["avg_best_score"]) for m in metrics) / n,
                "avg_primary_actions": sum(float(m["act_on_primary"]) for m in metrics) / n,
                "avg_routed_elsewhere": sum(float(m["routed_elsewhere"]) for m in metrics) / n,
            }
        )

    learned = next(r for r in rows if r["policy"] == "learned_stop_vs_act")
    heuristic = next(r for r in rows if r["policy"] == "heuristic_gain_gap")
    uncertainty = next(r for r in rows if r["policy"] == "uncertainty_entropy_only")

    metrics = {
        "learned_vs_heuristic_accuracy_margin": float(learned["accuracy"] - heuristic["accuracy"]),
        "learned_vs_uncertainty_accuracy_margin": float(learned["accuracy"] - uncertainty["accuracy"]),
        "learned_vs_heuristic_best_score_margin": float(learned["avg_best_score"] - heuristic["avg_best_score"]),
    }
    return StopVsActEvalArtifacts(metrics=metrics, comparison_rows=rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")
