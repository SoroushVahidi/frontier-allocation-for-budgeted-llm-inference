#!/usr/bin/env python3
"""Build reproducible target-fidelity pair-construction regimes from brute-force labels."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _canonical_label_for_pair(bi: str, bj: str, winner: str) -> int:
    return 1 if winner == bi else 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build target-fidelity pair regimes")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_targets")
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--pair-strategies",
        default="all_pairs,top_vs_rest,adjacent_rank,high_margin_only,uncertainty_filtered,quality_mixed_trust,partial_order_incomparable,penalized_marginal_defer,opportunity_intensity_weighted,opportunity_intensity_weighted_no_outside_norm",
        help="comma-separated strategies",
    )
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--high-margin-threshold", type=float, default=0.08)
    p.add_argument("--max-pair-std", type=float, default=0.08)
    p.add_argument("--exact-labels-dir", default="")
    p.add_argument("--promote-exact-over-approx", action="store_true")
    p.add_argument("--min-relative-margin", type=float, default=0.0)
    p.add_argument("--tie-abs-margin-threshold", type=float, default=0.03)
    p.add_argument("--tie-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--tie-std-threshold", type=float, default=0.08)
    p.add_argument("--tie-use-near-tie-flag", action="store_true")
    p.add_argument("--tie-include-approx", action="store_true")
    p.add_argument("--tie-require-exact-or-mixed", action="store_true")
    p.add_argument("--low-trust-near-tie-approx-weight", type=float, default=0.35)
    p.add_argument("--medium-trust-approx-weight", type=float, default=0.7)
    p.add_argument("--exact-trust-weight", type=float, default=1.15)
    p.add_argument("--low-trust-std-threshold", type=float, default=0.08)
    p.add_argument(
        "--tie-policy",
        choices=["legacy_or", "davidson_close_call"],
        default="legacy_or",
        help="Tie-assignment policy. davidson_close_call requires closeness + ambiguity risk.",
    )
    p.add_argument("--penalized-lambda", type=float, default=0.10)
    p.add_argument(
        "--penalized-delta-c-mode",
        choices=["constant_one", "inverse_remaining_budget", "branch_feature_proxy_v1"],
        default="constant_one",
    )
    p.add_argument("--penalized-tau-base", type=float, default=0.02)
    p.add_argument("--penalized-tau-relative-scale", type=float, default=0.10)
    p.add_argument("--penalized-tau-uncertainty-scale", type=float, default=0.50)
    p.add_argument("--penalized-tau-budget-scale", type=float, default=0.05)
    p.add_argument(
        "--penalized-tau-mode",
        choices=["legacy_additive_v1", "selective_ambiguity_gate_v1"],
        default="legacy_additive_v1",
    )
    p.add_argument("--penalized-tau-easy-uncertainty-multiplier", type=float, default=0.20)
    p.add_argument("--penalized-tau-easy-budget-multiplier", type=float, default=0.00)
    p.add_argument("--penalized-tau-gap-cap-multiplier", type=float, default=0.0)
    p.add_argument("--opportunity-intensity-eps", type=float, default=1e-6)
    p.add_argument("--opportunity-intensity-tau", type=float, default=0.05)
    p.add_argument("--opportunity-intensity-w-min", type=float, default=0.50)
    p.add_argument("--opportunity-intensity-w-max", type=float, default=4.00)
    p.add_argument("--opportunity-intensity-final-min", type=float, default=0.70)
    p.add_argument("--opportunity-intensity-final-max", type=float, default=1.60)
    return p.parse_args()


def _augment_pair_row(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    near_tie_margin: float,
    pair_type: str,
) -> dict[str, Any]:
    out = dict(row)
    margin = float(out.get("margin", 0.0))
    denom = max(abs(float(cand_i.get("estimated_value_if_allocate_next", 0.0))), abs(float(cand_j.get("estimated_value_if_allocate_next", 0.0))), 1e-6)
    std_i = float(cand_i.get("allocation_value_std", 0.0))
    std_j = float(cand_j.get("allocation_value_std", 0.0))
    out["margin_abs"] = abs(margin)
    out["relative_margin"] = abs(margin) / denom
    out["near_tie_flag"] = bool(abs(margin) <= float(near_tie_margin))
    out["pair_uncertainty_std_mean"] = 0.5 * (std_i + std_j)
    out["pair_uncertainty_std_max"] = max(std_i, std_j)
    mode_i = str(cand_i.get("mode", "unknown"))
    mode_j = str(cand_j.get("mode", "unknown"))
    out["pair_mode_provenance"] = mode_i if mode_i == mode_j else "mixed"
    out["outside_gap_i"] = float(cand_i.get("branch_vs_outside_gap", 0.0))
    out["outside_gap_j"] = float(cand_j.get("branch_vs_outside_gap", 0.0))
    out["outside_gap_abs_diff"] = abs(out["outside_gap_i"] - out["outside_gap_j"])
    out["pair_type"] = pair_type
    out["pair_quality_version"] = "branch_pair_quality_v1"
    return out


def _annotate_ambiguous_pair(
    row: dict[str, Any],
    *,
    tie_policy: str,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
    tie_use_near_tie_flag: bool,
    tie_include_approx: bool,
    tie_require_exact_or_mixed: bool,
) -> dict[str, Any]:
    out = dict(row)
    pair_mode = str(out.get("pair_mode_provenance", "unknown"))
    eligible_mode = True
    if (not tie_include_approx) and pair_mode == "approx":
        eligible_mode = False
    if tie_require_exact_or_mixed and pair_mode not in {"exact", "mixed"}:
        eligible_mode = False
    margin_close = float(out.get("margin_abs", 0.0)) <= float(tie_abs_margin_threshold)
    relative_close = float(out.get("relative_margin", 1e9)) <= float(tie_relative_margin_threshold)
    near_close = bool(out.get("near_tie_flag", False)) if tie_use_near_tie_flag else False
    std_high = float(out.get("pair_uncertainty_std_mean", 0.0)) >= float(tie_std_threshold)
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))
    close_call = bool(margin_close or relative_close or near_close)
    ambiguous_risk = bool(std_high or adjacent or disagreement_risk)

    triggers: list[str] = []
    if margin_close:
        triggers.append("abs_margin")
    if relative_close:
        triggers.append("relative_margin")
    if near_close:
        triggers.append("near_tie_flag")
    if std_high:
        triggers.append("uncertainty_std")
    if adjacent:
        triggers.append("adjacent_rank")
    if disagreement_risk:
        triggers.append("exact_vs_approx_disagreement_risk")

    if tie_policy == "davidson_close_call":
        ambiguous = bool(eligible_mode and close_call and ambiguous_risk)
    else:
        ambiguous = bool(eligible_mode and len(triggers) > 0)

    out["ambiguous_tie_target"] = ambiguous
    out["ambiguous_tie_reasons"] = triggers
    out["tie_policy"] = str(tie_policy)
    out["davidson_close_call_flag"] = bool(close_call and ambiguous_risk)
    out["ternary_label_name"] = "tie" if ambiguous else ("i_wins" if int(out.get("label", out.get("preference", 0))) == 1 else "j_wins")
    return out


def _annotate_soft_probabilistic_target(
    row: dict[str, Any],
    *,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
    tie_use_near_tie_flag: bool,
) -> dict[str, Any]:
    out = dict(row)
    margin_abs = float(out.get("margin_abs", 0.0))
    rel_margin = float(out.get("relative_margin", 1e9))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    near_tie = bool(out.get("near_tie_flag", False)) if tie_use_near_tie_flag else False
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))

    abs_scale = max(float(tie_abs_margin_threshold), 1e-6)
    rel_scale = max(float(tie_relative_margin_threshold), 1e-6)
    std_scale = max(float(tie_std_threshold), 1e-6)

    abs_close = math.exp(-margin_abs / abs_scale)
    rel_close = math.exp(-rel_margin / rel_scale)
    near_close = 0.95 if near_tie else 0.0
    close_strength = max(abs_close, rel_close, near_close)

    std_strength = min(1.0, pair_std / std_scale)
    adjacent_strength = 0.85 if adjacent else 0.0
    disagreement_strength = 1.0 if disagreement_risk else 0.0
    ambiguity_strength = max(std_strength, adjacent_strength, disagreement_strength)

    tie_prob = close_strength * (0.55 + 0.45 * ambiguity_strength)
    easy_pair = (
        margin_abs > (2.0 * abs_scale)
        and rel_margin > (2.0 * rel_scale)
        and pair_std < (0.5 * std_scale)
        and (not adjacent)
    )
    if easy_pair:
        tie_prob = min(tie_prob, 0.02)
    tie_prob = min(max(tie_prob, 0.01), 0.98)

    directional_mass = 1.0 - tie_prob
    directional_softness = max(0.0, 1.0 - min(1.0, margin_abs / max(2.0 * abs_scale, 1e-6)))
    loser_spill = directional_mass * 0.25 * directional_softness
    winner_mass = directional_mass - loser_spill
    label = int(out.get("label", out.get("preference", 0)))
    if label == 1:
        p_i, p_j = winner_mass, loser_spill
    else:
        p_i, p_j = loser_spill, winner_mass

    z = max(1e-8, p_i + tie_prob + p_j)
    p_i /= z
    tie_prob /= z
    p_j /= z
    out["soft_target_prob_i_wins"] = p_i
    out["soft_target_prob_tie"] = tie_prob
    out["soft_target_prob_j_wins"] = p_j
    out["soft_target_entropy"] = -sum(p * math.log(max(p, 1e-12)) for p in [p_i, tie_prob, p_j])
    out["soft_target_source"] = "davidson_soft_prob_v1"
    return out


def _assign_supervision_reliability(
    row: dict[str, Any],
    *,
    low_trust_near_tie_approx_weight: float,
    medium_trust_approx_weight: float,
    exact_trust_weight: float,
    low_trust_std_threshold: float,
) -> dict[str, Any]:
    out = dict(row)
    pair_mode = str(out.get("pair_mode_provenance", "unknown"))
    pair_type = str(out.get("pair_type", "generic"))
    near_tie = bool(out.get("near_tie_flag", False))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    label_source = str(out.get("label_source", ""))
    is_exact = pair_mode in {"exact", "mixed"} or label_source.startswith("exact")

    trust_tier = "medium"
    weight = float(medium_trust_approx_weight)
    keep_in_quality_mixed_trust = True

    if is_exact:
        trust_tier = "high_exact"
        weight = float(exact_trust_weight)
    elif (pair_type == "adjacent_rank") and near_tie and pair_std >= float(low_trust_std_threshold):
        trust_tier = "low_approx_near_tie_adjacent_high_std"
        weight = float(low_trust_near_tie_approx_weight)
        keep_in_quality_mixed_trust = False
    elif near_tie:
        trust_tier = "medium_approx_near_tie"
        weight = float(low_trust_near_tie_approx_weight)
    elif pair_std <= float(low_trust_std_threshold):
        trust_tier = "high_approx_easy"
        weight = 1.0

    out["supervision_trust_tier"] = trust_tier
    out["supervision_reliability_weight"] = max(weight, 1e-8)
    out["keep_in_quality_mixed_trust"] = bool(keep_in_quality_mixed_trust)
    return out


def _annotate_incomparable_pair(
    row: dict[str, Any],
    *,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
    tie_include_approx: bool,
    tie_require_exact_or_mixed: bool,
) -> dict[str, Any]:
    """Conservative unresolved/incomparability annotation.

    Semantics:
    - "tie" (Davidson-style) is a close preference.
    - "incomparable" here means insufficient evidence to force ordering.
    """
    out = dict(row)
    pair_mode = str(out.get("pair_mode_provenance", "unknown"))
    eligible_mode = True
    if (not tie_include_approx) and pair_mode == "approx":
        eligible_mode = False
    if tie_require_exact_or_mixed and pair_mode not in {"exact", "mixed"}:
        eligible_mode = False

    margin_abs = float(out.get("margin_abs", 0.0))
    rel_margin = float(out.get("relative_margin", 1e9))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    near_tie = bool(out.get("near_tie_flag", False))
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))

    # Conservative unresolved zone: require simultaneous absolute+relative closeness
    # plus at least one explicit ambiguity risk signal.
    abs_close = margin_abs <= float(tie_abs_margin_threshold)
    rel_close = rel_margin <= float(tie_relative_margin_threshold)
    std_high = pair_std >= float(tie_std_threshold)
    risk_signal = bool(std_high or adjacent or disagreement_risk)

    incomparable = bool(eligible_mode and abs_close and rel_close and near_tie and risk_signal)

    reasons: list[str] = []
    if abs_close:
        reasons.append("abs_margin")
    if rel_close:
        reasons.append("relative_margin")
    if near_tie:
        reasons.append("near_tie_flag")
    if std_high:
        reasons.append("uncertainty_std")
    if adjacent:
        reasons.append("adjacent_rank")
    if disagreement_risk:
        reasons.append("exact_vs_approx_disagreement_risk")

    label = int(out.get("label", out.get("preference", 0)))
    out["partial_order_incomparable_target"] = incomparable
    out["partial_order_incomparable_reasons"] = reasons
    out["partial_order_label"] = 1 if incomparable else (2 if label == 1 else 0)
    out["partial_order_label_name"] = "incomparable" if incomparable else ("i_wins" if label == 1 else "j_wins")
    out["partial_order_policy"] = "conservative_close_call_incomparable_v1"
    return out


def _delta_c_for_candidate(*, candidate_row: dict[str, Any], remaining_budget: float, mode: str) -> tuple[float, dict[str, float]]:
    mode_name = str(mode).strip().lower()
    if mode_name == "inverse_remaining_budget":
        c = 1.0 / max(1.0, float(remaining_budget))
        return c, {"base": c}
    if mode_name == "branch_feature_proxy_v1":
        f1 = candidate_row.get("features_branch_v1", {}) if isinstance(candidate_row.get("features_branch_v1"), dict) else {}
        depth = float(f1.get("depth", 0.0))
        verify_count = float(f1.get("verify_count", 0.0))
        stalled_steps = float(f1.get("stalled_steps", 0.0))
        branch_age = float(f1.get("branch_age", 0.0))
        alloc_std = float(candidate_row.get("allocation_value_std", 0.0))
        budget_scale = max(1.0, float(remaining_budget) + 1.0)
        depth_term = depth / budget_scale
        age_term = branch_age / budget_scale
        verify_term = verify_count / max(1.0, depth)
        cost = (
            1.0
            + 0.35 * depth_term
            + 0.45 * verify_term
            + 0.25 * stalled_steps
            + 0.30 * alloc_std
            + 0.20 * age_term
        )
        return cost, {
            "depth_term": depth_term,
            "verify_term": verify_term,
            "stalled_steps_term": stalled_steps,
            "allocation_std_term": alloc_std,
            "branch_age_term": age_term,
            "base": 1.0,
        }
    return 1.0, {"base": 1.0}


def _annotate_penalized_marginal_defer_pair(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    penalized_lambda: float,
    delta_c_mode: str,
    tau_base: float,
    tau_relative_scale: float,
    tau_uncertainty_scale: float,
    tau_budget_scale: float,
    tau_mode: str,
    tau_easy_uncertainty_multiplier: float,
    tau_easy_budget_multiplier: float,
    tau_gap_cap_multiplier: float,
    near_tie_margin: float,
) -> dict[str, Any]:
    out = dict(row)
    remaining_budget = float(out.get("remaining_budget", cand_i.get("remaining_budget", cand_j.get("remaining_budget", 0.0))))
    delta_u_i = float(cand_i.get("estimated_value_if_allocate_next", out.get("pair_value_i", 0.0)))
    delta_u_j = float(cand_j.get("estimated_value_if_allocate_next", out.get("pair_value_j", 0.0)))
    delta_c_i, delta_c_i_components = _delta_c_for_candidate(candidate_row=cand_i, remaining_budget=remaining_budget, mode=delta_c_mode)
    delta_c_j, delta_c_j_components = _delta_c_for_candidate(candidate_row=cand_j, remaining_budget=remaining_budget, mode=delta_c_mode)
    penalized_i = delta_u_i - float(penalized_lambda) * delta_c_i
    penalized_j = delta_u_j - float(penalized_lambda) * delta_c_j
    penalized_gap = penalized_i - penalized_j
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    tau_mode_name = str(tau_mode).strip().lower()
    is_hard_ambiguity = bool(
        bool(out.get("near_tie_flag", False))
        or str(out.get("pair_type", "")) == "adjacent_rank"
        or bool(out.get("exact_vs_approx_disagreement_risk", False))
        or bool(out.get("davidson_close_call_flag", False))
    )
    base_term = float(tau_base) + float(tau_relative_scale) * max(abs(delta_u_i), abs(delta_u_j))
    uncertainty_term = float(tau_uncertainty_scale) * pair_std
    budget_term = float(tau_budget_scale) / max(1.0, remaining_budget + 1.0)
    if tau_mode_name == "selective_ambiguity_gate_v1":
        if not is_hard_ambiguity:
            uncertainty_term *= float(tau_easy_uncertainty_multiplier)
            budget_term *= float(tau_easy_budget_multiplier)
    tau_raw = base_term + uncertainty_term + budget_term
    tau_state = tau_raw
    if tau_mode_name == "selective_ambiguity_gate_v1" and float(tau_gap_cap_multiplier) > 0.0:
        cap = float(tau_gap_cap_multiplier) * max(abs(penalized_gap), float(tau_base), 1e-6)
        tau_state = min(tau_raw, cap)

    left_better = penalized_gap > (tau_state)
    right_better = (-penalized_gap) > (tau_state)
    defer = bool((not left_better) and (not right_better))

    out["label"] = 1 if penalized_gap >= 0.0 else 0
    out["preference"] = int(out["label"])
    out["margin"] = float(penalized_gap)
    out["margin_abs"] = abs(float(penalized_gap))
    out["relative_margin"] = abs(float(penalized_gap)) / max(abs(penalized_i), abs(penalized_j), 1e-6)
    out["near_tie_flag"] = bool(out["margin_abs"] <= float(near_tie_margin))

    out["delta_u_i"] = float(delta_u_i)
    out["delta_u_j"] = float(delta_u_j)
    out["delta_c_i"] = float(delta_c_i)
    out["delta_c_j"] = float(delta_c_j)
    out["penalized_marginal_value_i"] = float(penalized_i)
    out["penalized_marginal_value_j"] = float(penalized_j)
    out["penalized_marginal_gap"] = float(penalized_gap)
    out["penalized_lambda"] = float(penalized_lambda)
    out["penalized_tau_state"] = float(tau_state)
    out["penalized_tau_components"] = {
        "mode": str(tau_mode_name),
        "hard_ambiguity_flag": bool(is_hard_ambiguity),
        "base": float(tau_base),
        "relative_scale": float(tau_relative_scale),
        "uncertainty_scale": float(tau_uncertainty_scale),
        "budget_scale": float(tau_budget_scale),
        "easy_uncertainty_multiplier": float(tau_easy_uncertainty_multiplier),
        "easy_budget_multiplier": float(tau_easy_budget_multiplier),
        "gap_cap_multiplier": float(tau_gap_cap_multiplier),
        "base_term": float(base_term),
        "uncertainty_term_effective": float(uncertainty_term),
        "budget_term_effective": float(budget_term),
        "tau_raw_pre_cap": float(tau_raw),
    }
    out["penalized_delta_c_mode"] = str(delta_c_mode)
    out["penalized_delta_c_i_components"] = delta_c_i_components
    out["penalized_delta_c_j_components"] = delta_c_j_components
    out["penalized_ternary_label"] = 2 if left_better else (0 if right_better else 1)
    out["penalized_ternary_label_name"] = "left_better" if left_better else ("right_better" if right_better else "defer")
    out["penalized_marginal_defer_target"] = bool(defer)

    out["ternary_defer_label"] = int(out["penalized_ternary_label"])
    out["ternary_defer_label_name"] = (
        "allocate_to_branch_i"
        if int(out["ternary_defer_label"]) == 2
        else ("allocate_to_branch_j" if int(out["ternary_defer_label"]) == 0 else "defer_or_outside_option")
    )
    out["ternary_defer_label_source"] = "penalized_marginal_value_with_budget_price"
    out["defer_target_mode"] = "precomputed_penalized_marginal"
    out["label_source"] = "penalized_marginal_value_with_budget_price"
    if defer:
        reasons = list(out.get("ambiguous_tie_reasons", []))
        if "penalized_tau_defer" not in reasons:
            reasons.append("penalized_tau_defer")
        out["ambiguous_tie_target"] = True
        out["ambiguous_tie_reasons"] = reasons
    return out


def _annotate_opportunity_intensity_weight(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    tau: float,
    eps: float,
    w_min: float,
    w_max: float,
    use_outside_norm: bool,
) -> dict[str, Any]:
    out = dict(row)
    vi = float(cand_i.get("estimated_value_if_allocate_next", out.get("pair_value_i", 0.0)))
    vj = float(cand_j.get("estimated_value_if_allocate_next", out.get("pair_value_j", 0.0)))
    outside = float(out.get("outside_option_value_estimate", 0.0)) if use_outside_norm else 0.0
    denom = abs(vi) + abs(vj) + (abs(outside) if use_outside_norm else 0.0) + max(float(eps), 1e-12)
    intensity = abs(vi - vj) / max(denom, 1e-12)
    raw_weight = 1.0 / max(float(intensity) + float(tau), 1e-12)
    clipped_weight = min(max(float(raw_weight), float(w_min)), float(w_max))

    out["opportunity_value_i"] = float(vi)
    out["opportunity_value_j"] = float(vj)
    out["opportunity_outside_value"] = float(outside)
    out["opportunity_intensity_raw"] = float(intensity)
    out["opportunity_intensity_weight_raw"] = float(raw_weight)
    out["opportunity_intensity_weight"] = float(clipped_weight)
    out["opportunity_intensity_used_outside_norm"] = bool(use_outside_norm)
    out["opportunity_intensity_weight_source"] = "opportunity_intensity_v1"
    out["opportunity_intensity_tau"] = float(tau)
    out["opportunity_intensity_eps"] = float(eps)
    out["opportunity_intensity_w_min"] = float(w_min)
    out["opportunity_intensity_w_max"] = float(w_max)
    return out


def _apply_opportunity_weight_normalization(
    rows: list[dict[str, Any]],
    *,
    final_min: float,
    final_max: float,
) -> list[dict[str, Any]]:
    if not rows:
        return rows

    raw_weights = [float(r.get("opportunity_intensity_weight", 1.0)) for r in rows]
    w_lo = min(raw_weights)
    w_hi = max(raw_weights)
    target_span = max(float(final_max) - float(final_min), 0.0)

    for r in rows:
        w = float(r.get("opportunity_intensity_weight", 1.0))
        if (w_hi - w_lo) <= 1e-12 or target_span <= 1e-12:
            final_mult = 1.0
        else:
            final_mult = float(final_min) + target_span * ((w - w_lo) / max(w_hi - w_lo, 1e-12))
        r["opportunity_intensity_weight_final"] = float(final_mult)
        r["opportunity_intensity_weight_final_min"] = float(final_min)
        r["opportunity_intensity_weight_final_max"] = float(final_max)
        r["opportunity_intensity_weight_global_min_observed"] = float(w_lo)
        r["opportunity_intensity_weight_global_max_observed"] = float(w_hi)
        r["opportunity_intensity_weight_normalization"] = "global_minmax_v1"
        r["supervision_reliability_weight"] = float(r.get("supervision_reliability_weight", 1.0)) * float(final_mult)
        r["opportunity_intensity_baked_into_supervision_reliability_weight"] = True
    return rows


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    out_root = Path(args.output_dir) / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairwise = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    cand_map: dict[tuple[str, str], dict[str, Any]] = {}
    state_to_cands: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        sid = str(c["state_id"])
        bid = str(c["branch_id"])
        cand_map[(sid, bid)] = c
        state_to_cands.setdefault(sid, []).append(c)

    base_pair_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for p in pairwise:
        k = _pair_key(str(p["state_id"]), str(p["branch_i"]), str(p["branch_j"]))
        base_pair_map[k] = p

    exact_pair_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    if args.exact_labels_dir:
        exact_dir = Path(args.exact_labels_dir)
        if (exact_dir / "pairwise_labels.jsonl").exists():
            for p in _read_jsonl(exact_dir / "pairwise_labels.jsonl"):
                exact_pair_map[_pair_key(str(p["state_id"]), str(p["branch_i"]), str(p["branch_j"]))] = p

    strategies = [s.strip() for s in args.pair_strategies.split(",") if s.strip()]
    run_manifest: dict[str, Any] = {
        "run_id": args.run_id,
        "labels_dir": str(labels_dir),
        "strategies": strategies,
        "config": {
            "near_tie_margin": args.near_tie_margin,
            "high_margin_threshold": args.high_margin_threshold,
            "max_pair_std": args.max_pair_std,
            "promote_exact_over_approx": bool(args.promote_exact_over_approx),
            "min_relative_margin": args.min_relative_margin,
            "exact_labels_dir": args.exact_labels_dir,
            "tie_abs_margin_threshold": args.tie_abs_margin_threshold,
            "tie_relative_margin_threshold": args.tie_relative_margin_threshold,
            "tie_std_threshold": args.tie_std_threshold,
            "tie_use_near_tie_flag": bool(args.tie_use_near_tie_flag),
            "tie_include_approx": bool(args.tie_include_approx),
            "tie_require_exact_or_mixed": bool(args.tie_require_exact_or_mixed),
            "low_trust_near_tie_approx_weight": args.low_trust_near_tie_approx_weight,
            "medium_trust_approx_weight": args.medium_trust_approx_weight,
            "exact_trust_weight": args.exact_trust_weight,
            "low_trust_std_threshold": args.low_trust_std_threshold,
            "tie_policy": args.tie_policy,
            "penalized_lambda": args.penalized_lambda,
            "penalized_delta_c_mode": args.penalized_delta_c_mode,
            "penalized_tau_base": args.penalized_tau_base,
            "penalized_tau_relative_scale": args.penalized_tau_relative_scale,
            "penalized_tau_uncertainty_scale": args.penalized_tau_uncertainty_scale,
            "penalized_tau_budget_scale": args.penalized_tau_budget_scale,
            "penalized_tau_mode": args.penalized_tau_mode,
            "penalized_tau_easy_uncertainty_multiplier": args.penalized_tau_easy_uncertainty_multiplier,
            "penalized_tau_easy_budget_multiplier": args.penalized_tau_easy_budget_multiplier,
            "penalized_tau_gap_cap_multiplier": args.penalized_tau_gap_cap_multiplier,
            "opportunity_intensity_eps": args.opportunity_intensity_eps,
            "opportunity_intensity_tau": args.opportunity_intensity_tau,
            "opportunity_intensity_w_min": args.opportunity_intensity_w_min,
            "opportunity_intensity_w_max": args.opportunity_intensity_w_max,
            "opportunity_intensity_final_min": args.opportunity_intensity_final_min,
            "opportunity_intensity_final_max": args.opportunity_intensity_final_max,
        },
        "regimes": {},
    }

    for strat in strategies:
        kept: list[dict[str, Any]] = []
        for sid, cand_rows in state_to_cands.items():
            ranked = sorted(cand_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
            top_branch = str(ranked[0]["branch_id"]) if ranked else ""
            neighbor_pairs = set()
            for i in range(max(0, len(ranked) - 1)):
                neighbor_pairs.add(_pair_key(sid, str(ranked[i]["branch_id"]), str(ranked[i + 1]["branch_id"])))

            for i in range(len(ranked)):
                for j in range(i + 1, len(ranked)):
                    bi = str(ranked[i]["branch_id"])
                    bj = str(ranked[j]["branch_id"])
                    k = _pair_key(sid, bi, bj)
                    base = dict(base_pair_map.get(k, {
                        "state_id": sid,
                        "example_id": ranked[i].get("example_id", ""),
                        "dataset_name": ranked[i].get("dataset_name", "unknown"),
                        "remaining_budget": ranked[i].get("remaining_budget", 0),
                        "branch_i": bi,
                        "branch_j": bj,
                    }))

                    vi = float(cand_map[(sid, bi)].get("estimated_value_if_allocate_next", 0.0))
                    vj = float(cand_map[(sid, bj)].get("estimated_value_if_allocate_next", 0.0))
                    winner = bi if vi >= vj else bj
                    if "preference" not in base and "label" not in base:
                        base["preference"] = _canonical_label_for_pair(str(base.get("branch_i", bi)), str(base.get("branch_j", bj)), winner)
                    else:
                        base["preference"] = int(base.get("preference", base.get("label", 0)))
                    base["label"] = int(base["preference"])
                    if "margin" not in base:
                        base["margin"] = vi - vj if str(base.get("branch_i", bi)) == bi else vj - vi

                    if args.promote_exact_over_approx and k in exact_pair_map:
                        ex = exact_pair_map[k]
                        ex_bi = str(ex.get("branch_i", bi))
                        ex_bj = str(ex.get("branch_j", bj))
                        base["branch_i"] = ex_bi
                        base["branch_j"] = ex_bj
                        base["preference"] = int(ex.get("preference", ex.get("label", 0)))
                        base["label"] = int(base["preference"])
                        base["margin"] = float(ex.get("margin", base["margin"]))
                        base["label_source"] = "exact_promoted"
                        base["replaced_approx_label"] = True
                        base["pair_mode_provenance"] = "exact"
                    else:
                        src_mode = str(cand_map[(sid, bi)].get("mode", "unknown"))
                        base["label_source"] = "exact_original" if src_mode == "exact" else "approx_original"
                        base["replaced_approx_label"] = False

                    pair_type = "generic"
                    if bi == top_branch or bj == top_branch:
                        pair_type = "top_vs_rest"
                    if k in neighbor_pairs:
                        pair_type = "adjacent_rank"

                    prow = _augment_pair_row(
                        base,
                        cand_i=cand_map[(sid, str(base["branch_i"]))],
                        cand_j=cand_map[(sid, str(base["branch_j"]))],
                        near_tie_margin=float(args.near_tie_margin),
                        pair_type=pair_type,
                    )

                    if float(prow.get("relative_margin", 0.0)) < float(args.min_relative_margin):
                        continue

                    keep = False
                    if strat == "all_pairs":
                        keep = True
                    elif strat == "top_vs_rest":
                        keep = prow["pair_type"] == "top_vs_rest"
                    elif strat == "adjacent_rank":
                        keep = prow["pair_type"] == "adjacent_rank"
                    elif strat == "high_margin_only":
                        keep = float(prow["margin_abs"]) >= float(args.high_margin_threshold)
                    elif strat == "uncertainty_filtered":
                        keep = (
                            float(prow["pair_uncertainty_std_mean"]) <= float(args.max_pair_std)
                            and not bool(prow["near_tie_flag"])
                        )
                    elif strat == "quality_mixed_trust":
                        keep = True
                    elif strat == "davidson_tie_aware":
                        keep = True
                    elif strat == "soft_prob_tie_aware":
                        keep = True
                    elif strat == "partial_order_incomparable":
                        keep = True
                    elif strat == "penalized_marginal_defer":
                        keep = True
                    elif strat == "opportunity_intensity_weighted":
                        keep = True
                    elif strat == "opportunity_intensity_weighted_no_outside_norm":
                        keep = True
                    else:
                        raise ValueError(f"Unknown strategy: {strat}")

                    if keep:
                        tie_policy_for_strategy = str(args.tie_policy)
                        if strat == "all_pairs":
                            tie_policy_for_strategy = "legacy_or"
                        elif strat in {"davidson_tie_aware", "soft_prob_tie_aware"}:
                            tie_policy_for_strategy = "davidson_close_call"

                        annotated = _annotate_ambiguous_pair(
                            prow,
                            tie_policy=tie_policy_for_strategy,
                            tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                            tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                            tie_std_threshold=float(args.tie_std_threshold),
                            tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                            tie_include_approx=bool(args.tie_include_approx),
                            tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
                        )
                        annotated = _assign_supervision_reliability(
                            annotated,
                            low_trust_near_tie_approx_weight=float(args.low_trust_near_tie_approx_weight),
                            medium_trust_approx_weight=float(args.medium_trust_approx_weight),
                            exact_trust_weight=float(args.exact_trust_weight),
                            low_trust_std_threshold=float(args.low_trust_std_threshold),
                        )
                        if strat == "quality_mixed_trust" and (not bool(annotated.get("keep_in_quality_mixed_trust", True))):
                            continue
                        if strat == "soft_prob_tie_aware":
                            annotated = _annotate_soft_probabilistic_target(
                                annotated,
                                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                                tie_std_threshold=float(args.tie_std_threshold),
                                tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                            )
                        if strat == "partial_order_incomparable":
                            annotated = _annotate_incomparable_pair(
                                annotated,
                                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                                tie_std_threshold=float(args.tie_std_threshold),
                                tie_include_approx=bool(args.tie_include_approx),
                                tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
                            )
                        if strat == "penalized_marginal_defer":
                            annotated = _annotate_penalized_marginal_defer_pair(
                                annotated,
                                cand_i=cand_map[(sid, str(annotated["branch_i"]))],
                                cand_j=cand_map[(sid, str(annotated["branch_j"]))],
                                penalized_lambda=float(args.penalized_lambda),
                                delta_c_mode=str(args.penalized_delta_c_mode),
                                tau_base=float(args.penalized_tau_base),
                                tau_relative_scale=float(args.penalized_tau_relative_scale),
                                tau_uncertainty_scale=float(args.penalized_tau_uncertainty_scale),
                                tau_budget_scale=float(args.penalized_tau_budget_scale),
                                tau_mode=str(args.penalized_tau_mode),
                                tau_easy_uncertainty_multiplier=float(args.penalized_tau_easy_uncertainty_multiplier),
                                tau_easy_budget_multiplier=float(args.penalized_tau_easy_budget_multiplier),
                                tau_gap_cap_multiplier=float(args.penalized_tau_gap_cap_multiplier),
                                near_tie_margin=float(args.near_tie_margin),
                            )
                        if strat in {"opportunity_intensity_weighted", "opportunity_intensity_weighted_no_outside_norm"}:
                            annotated = _annotate_opportunity_intensity_weight(
                                annotated,
                                cand_i=cand_map[(sid, str(annotated["branch_i"]))],
                                cand_j=cand_map[(sid, str(annotated["branch_j"]))],
                                tau=float(args.opportunity_intensity_tau),
                                eps=float(args.opportunity_intensity_eps),
                                w_min=float(args.opportunity_intensity_w_min),
                                w_max=float(args.opportunity_intensity_w_max),
                                use_outside_norm=(strat == "opportunity_intensity_weighted"),
                            )
                        kept.append(annotated)

        if strat in {"opportunity_intensity_weighted", "opportunity_intensity_weighted_no_outside_norm"}:
            kept = _apply_opportunity_weight_normalization(
                kept,
                final_min=float(args.opportunity_intensity_final_min),
                final_max=float(args.opportunity_intensity_final_max),
            )

        out_dir = out_root / f"regime_{strat}"
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out_dir / "candidate_labels.jsonl", candidates)
        _write_jsonl(out_dir / "pairwise_labels.jsonl", kept)
        _write_jsonl(out_dir / "state_summaries.jsonl", states)

        summary = {
            "strategy": strat,
            "pairs": len(kept),
            "near_tie_rate": (sum(1 for r in kept if bool(r.get("near_tie_flag", False))) / max(1, len(kept))),
            "ambiguous_tie_rate": (sum(1 for r in kept if bool(r.get("ambiguous_tie_target", False))) / max(1, len(kept))),
            "exact_or_promoted_rate": (
                sum(1 for r in kept if str(r.get("label_source", "")).startswith("exact")) / max(1, len(kept))
            ),
            "pair_type_counts": {
                "top_vs_rest": sum(1 for r in kept if r.get("pair_type") == "top_vs_rest"),
                "adjacent_rank": sum(1 for r in kept if r.get("pair_type") == "adjacent_rank"),
                "generic": sum(1 for r in kept if r.get("pair_type") == "generic"),
            },
            "mean_soft_tie_prob": (
                sum(float(r.get("soft_target_prob_tie", 0.0)) for r in kept) / max(1, len(kept))
            ),
            "partial_order_incomparable_rate": (
                sum(1 for r in kept if bool(r.get("partial_order_incomparable_target", False))) / max(1, len(kept))
            ),
            "penalized_left_better_rate": (
                sum(1 for r in kept if str(r.get("penalized_ternary_label_name", "")) == "left_better") / max(1, len(kept))
            ),
            "penalized_right_better_rate": (
                sum(1 for r in kept if str(r.get("penalized_ternary_label_name", "")) == "right_better") / max(1, len(kept))
            ),
            "penalized_defer_rate": (
                sum(1 for r in kept if str(r.get("penalized_ternary_label_name", "")) == "defer") / max(1, len(kept))
            ),
            "opportunity_intensity_weight_mean": (
                sum(float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in kept)
                / max(1, len(kept))
            ),
            "opportunity_intensity_weight_near_tie_mean": (
                sum(float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in kept if bool(r.get("near_tie_flag", False)))
                / max(1, sum(1 for r in kept if bool(r.get("near_tie_flag", False))))
            ),
            "opportunity_intensity_weight_non_near_tie_mean": (
                sum(
                    float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0)))
                    for r in kept
                    if (not bool(r.get("near_tie_flag", False)))
                )
                / max(1, sum(1 for r in kept if (not bool(r.get("near_tie_flag", False)))))
            ),
            "opportunity_intensity_weight_adjacent_mean": (
                sum(
                    float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0)))
                    for r in kept
                    if str(r.get("pair_type", "")) == "adjacent_rank"
                )
                / max(1, sum(1 for r in kept if str(r.get("pair_type", "")) == "adjacent_rank"))
            ),
            "opportunity_intensity_weight_non_adjacent_mean": (
                sum(
                    float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0)))
                    for r in kept
                    if str(r.get("pair_type", "")) != "adjacent_rank"
                )
                / max(1, sum(1 for r in kept if str(r.get("pair_type", "")) != "adjacent_rank"))
            ),
        }
        (out_dir / "target_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        run_manifest["regimes"][strat] = {
            "output_dir": str(out_dir),
            "summary": summary,
        }

    (out_root / "manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    md = ["# Branch-comparison target regimes", "", f"- run_id: `{args.run_id}`", "", "## Regimes", ""]
    for name, info in run_manifest["regimes"].items():
        s = info["summary"]
        md.append(f"- {name}: pairs={s['pairs']}, near_tie_rate={s['near_tie_rate']:.3f}, exact_or_promoted_rate={s['exact_or_promoted_rate']:.3f}")
    (out_root / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_root), "regimes": list(run_manifest["regimes"].keys())}, indent=2))


if __name__ == "__main__":
    main()
