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
        default="all_pairs,top_vs_rest,adjacent_rank,high_margin_only,uncertainty_filtered,quality_mixed_trust,partial_order_incomparable,penalized_marginal_defer,opportunity_intensity_weighted,opportunity_intensity_weighted_no_outside_norm,allocation_regret_target,allocation_regret_target_no_outside,multistep_branch_utility_target_k1,multistep_branch_utility_target_k2,multistep_branch_utility_target_k3,compute_response_curve_target_h123,rank_instability_target_v1",
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
    p.add_argument("--multistep-utility-lambda", type=float, default=0.35)
    p.add_argument("--response-curve-max-horizon", type=int, default=3)
    p.add_argument("--response-curve-score-w1", type=float, default=1.0)
    p.add_argument("--response-curve-score-w2", type=float, default=0.60)
    p.add_argument("--response-curve-score-w3", type=float, default=0.30)
    p.add_argument("--rank-instability-discount-gamma", type=float, default=0.8)
    p.add_argument("--rank-instability-margin-threshold", type=float, default=0.03)
    p.add_argument("--rank-instability-min-disagreement-count", type=int, default=1)
    return p.parse_args()


def _build_state_branch_index(candidates: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    per_state: dict[str, list[str]] = {}
    for row in candidates:
        sid = str(row.get("state_id", ""))
        bid = str(row.get("branch_id", ""))
        per_state.setdefault(sid, [])
        if bid not in per_state[sid]:
            per_state[sid].append(bid)
    for sid, bids in per_state.items():
        for idx, bid in enumerate(bids):
            out[(sid, bid)] = int(idx)
    return out


def _multistep_utility_target_for_candidate(
    candidate_row: dict[str, Any],
    *,
    state_id: str,
    branch_id: str,
    branch_index_map: dict[tuple[str, str], int],
    horizon_k: int,
    utility_lambda: float,
) -> dict[str, float]:
    est = float(candidate_row.get("estimated_value_if_allocate_next", 0.0))
    alloc = candidate_row.get("best_followup_allocation", [])
    alloc_vec = alloc if isinstance(alloc, list) else []
    branch_idx = int(branch_index_map.get((state_id, branch_id), 0))
    self_followup = float(alloc_vec[branch_idx]) if 0 <= branch_idx < len(alloc_vec) else 0.0
    if horizon_k <= 1:
        ratio = 0.0
        capped = 0.0
    else:
        capped = float(min(max(self_followup, 0.0), horizon_k - 1))
        ratio = capped / max(1.0, float(horizon_k - 1))
    utility_k = est * (1.0 + float(utility_lambda) * ratio)
    return {
        "multistep_target_horizon_k": float(horizon_k),
        "multistep_target_source": "best_followup_allocation_self_mass_proxy_v1",
        "multistep_target_utility_lambda": float(utility_lambda),
        "multistep_target_one_step_value": float(est),
        "multistep_target_self_followup_units_raw": float(self_followup),
        "multistep_target_self_followup_units_capped": float(capped),
        "multistep_target_self_followup_ratio": float(ratio),
        "multistep_branch_utility_target": float(utility_k),
        "multistep_branch_utility_delta_vs_onestep": float(utility_k - est),
    }


def _discounted_multistep_utility_target_for_candidate(
    candidate_row: dict[str, Any],
    *,
    state_id: str,
    branch_id: str,
    branch_index_map: dict[tuple[str, str], int],
    utility_lambda: float,
    discount_gamma: float,
    max_horizon: int = 3,
) -> dict[str, float]:
    gamma = float(discount_gamma)
    horizon = int(max(1, max_horizon))
    weighted_sum = 0.0
    weight_sum = 0.0
    horizon_values: dict[int, float] = {}
    horizon_weights: dict[int, float] = {}
    base_diag: dict[str, float] = {}
    for h in range(1, horizon + 1):
        diag = _multistep_utility_target_for_candidate(
            candidate_row,
            state_id=state_id,
            branch_id=branch_id,
            branch_index_map=branch_index_map,
            horizon_k=h,
            utility_lambda=utility_lambda,
        )
        val_h = float(diag["multistep_branch_utility_target"])
        wt_h = float(gamma ** float(h - 1))
        weighted_sum += wt_h * val_h
        weight_sum += wt_h
        horizon_values[h] = val_h
        horizon_weights[h] = wt_h
        if h == horizon:
            base_diag = dict(diag)
    denom = max(weight_sum, 1e-12)
    target_val = float(weighted_sum / denom)
    one_step = float(candidate_row.get("estimated_value_if_allocate_next", 0.0))
    out = {
        **base_diag,
        "multistep_target_source": "discounted_multistep_branch_utility_target_v1",
        "multistep_target_horizon_k": float(horizon),
        "multistep_target_discount_gamma": float(gamma),
        "multistep_target_discount_weights_sum": float(weight_sum),
        "multistep_target_discount_weight_h1": float(horizon_weights.get(1, 0.0)),
        "multistep_target_discount_weight_h2": float(horizon_weights.get(2, 0.0)),
        "multistep_target_discount_weight_h3": float(horizon_weights.get(3, 0.0)),
        "multistep_target_component_h1": float(horizon_values.get(1, 0.0)),
        "multistep_target_component_h2": float(horizon_values.get(2, 0.0)),
        "multistep_target_component_h3": float(horizon_values.get(3, 0.0)),
        "multistep_branch_utility_target": float(target_val),
        "multistep_branch_utility_delta_vs_onestep": float(target_val - one_step),
    }
    return out


def _parse_discounted_gamma_from_strategy(strategy: str) -> float | None:
    prefix = "discounted_multistep_branch_utility_target_gamma"
    if not str(strategy).startswith(prefix):
        return None
    encoded = str(strategy)[len(prefix) :]
    if not encoded:
        raise ValueError(f"Missing gamma suffix in discounted strategy: {strategy}")
    gamma = float(int(encoded)) / 100.0
    if gamma <= 0.0:
        raise ValueError(f"Gamma must be > 0 for discounted strategy: {strategy}")
    return gamma


def _compute_response_curve_target_for_candidate(
    candidate_row: dict[str, Any],
    *,
    state_id: str,
    branch_id: str,
    branch_index_map: dict[tuple[str, str], int],
    utility_lambda: float,
    max_horizon: int,
    score_weights: tuple[float, float, float],
) -> dict[str, Any]:
    horizon = int(max(1, max_horizon))
    per_horizon: dict[str, float] = {}
    for h in range(1, horizon + 1):
        diag = _multistep_utility_target_for_candidate(
            candidate_row,
            state_id=state_id,
            branch_id=branch_id,
            branch_index_map=branch_index_map,
            horizon_k=h,
            utility_lambda=utility_lambda,
        )
        per_horizon[f"h{h}"] = float(diag["multistep_branch_utility_target"])

    h1 = float(per_horizon.get("h1", 0.0))
    h2 = float(per_horizon.get("h2", h1))
    h3 = float(per_horizon.get("h3", h2))
    m1 = float(h1)
    m2 = float(h2 - h1)
    m3 = float(h3 - h2)
    w1, w2, w3 = score_weights
    scalar = float(w1 * m1 + w2 * m2 + w3 * m3)
    return {
        "compute_response_curve_target_version": "compute_response_curve_target_v1",
        "compute_response_curve_target_source": "multistep_self_followup_proxy_horizon_h1_h3",
        "compute_response_curve_horizons": [1, 2, 3],
        "compute_response_curve_values": [h1, h2, h3],
        "compute_response_curve_h1": h1,
        "compute_response_curve_h2": h2,
        "compute_response_curve_h3": h3,
        "compute_response_curve_marginal_m1": m1,
        "compute_response_curve_marginal_m2": m2,
        "compute_response_curve_marginal_m3": m3,
        "compute_response_curve_decision_scalar_version": "marginal_weighted_v1",
        "compute_response_curve_decision_scalar_w1": float(w1),
        "compute_response_curve_decision_scalar_w2": float(w2),
        "compute_response_curve_decision_scalar_w3": float(w3),
        "compute_response_curve_decision_scalar": scalar,
    }


def _statewise_rank_instability_signals(
    state_rows: list[dict[str, Any]],
    *,
    state_id: str,
    branch_index_map: dict[tuple[str, str], int],
    utility_lambda: float,
    discount_gamma: float,
    response_curve_max_horizon: int,
    response_curve_score_weights: tuple[float, float, float],
    margin_threshold: float,
    min_disagreement_count: int,
) -> dict[str, Any]:
    by_branch = {str(r.get("branch_id", "")): r for r in state_rows}
    signals: dict[str, dict[str, float]] = {
        "one_step": {},
        "multistep_k3": {},
        "discounted_gamma": {},
        "curve_scalar": {},
    }
    for bid, row in by_branch.items():
        one_step = float(row.get("estimated_value_if_allocate_next", 0.0))
        ms = _multistep_utility_target_for_candidate(
            row,
            state_id=state_id,
            branch_id=bid,
            branch_index_map=branch_index_map,
            horizon_k=3,
            utility_lambda=utility_lambda,
        )
        dms = _discounted_multistep_utility_target_for_candidate(
            row,
            state_id=state_id,
            branch_id=bid,
            branch_index_map=branch_index_map,
            utility_lambda=utility_lambda,
            discount_gamma=discount_gamma,
            max_horizon=3,
        )
        curve = _compute_response_curve_target_for_candidate(
            row,
            state_id=state_id,
            branch_id=bid,
            branch_index_map=branch_index_map,
            utility_lambda=utility_lambda,
            max_horizon=response_curve_max_horizon,
            score_weights=response_curve_score_weights,
        )
        signals["one_step"][bid] = one_step
        signals["multistep_k3"][bid] = float(ms["multistep_branch_utility_target"])
        signals["discounted_gamma"][bid] = float(dms["multistep_branch_utility_target"])
        signals["curve_scalar"][bid] = float(curve["compute_response_curve_decision_scalar"])

    top1_by_signal: dict[str, str] = {}
    top1_margin_by_signal: dict[str, float] = {}
    for name, vals in signals.items():
        ranked = sorted(vals.items(), key=lambda x: x[1], reverse=True)
        top1 = str(ranked[0][0]) if ranked else ""
        top2v = float(ranked[1][1]) if len(ranked) > 1 else float(ranked[0][1]) if ranked else 0.0
        top1_by_signal[name] = top1
        top1_margin_by_signal[name] = float(float(ranked[0][1]) - top2v) if ranked else 0.0

    unique_top1 = sorted(set(top1_by_signal.values()))
    disagreement_count = max(0, len(unique_top1) - 1)
    min_margin = min(top1_margin_by_signal.values()) if top1_margin_by_signal else 0.0
    unstable = bool(
        disagreement_count >= int(max(1, min_disagreement_count))
        and float(min_margin) <= float(margin_threshold)
    )
    score = float(min(1.0, 0.5 * disagreement_count + max(0.0, 1.0 - (min_margin / max(1e-6, margin_threshold))) * 0.5))

    pair_orientation: dict[tuple[str, str], dict[str, int]] = {}
    branch_ids = sorted(by_branch.keys())
    for i in range(len(branch_ids)):
        for j in range(i + 1, len(branch_ids)):
            bi, bj = branch_ids[i], branch_ids[j]
            per_signal = {}
            for sname, vals in signals.items():
                per_signal[sname] = 1 if float(vals.get(bi, 0.0)) >= float(vals.get(bj, 0.0)) else 0
            pair_orientation[(bi, bj)] = per_signal

    return {
        "state_id": state_id,
        "top1_by_signal": top1_by_signal,
        "top1_margin_by_signal": top1_margin_by_signal,
        "rank_instability_unique_top1_count": int(len(unique_top1)),
        "rank_instability_top1_disagreement_count": int(disagreement_count),
        "rank_instability_min_top1_margin_abs": float(min_margin),
        "rank_instability_state_score": float(score),
        "rank_instability_state_label": bool(unstable),
        "rank_instability_pair_orientations": pair_orientation,
        "rank_instability_signals": signals,
    }


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


def _annotate_allocation_regret_target(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    state_best_value: float,
    use_outside_option: bool,
    near_tie_margin: float,
) -> dict[str, Any]:
    """Consequence-aware allocation regret target.

    Direction remains pairwise-preference compatible, but supervision magnitude
    explicitly carries projected regret cost relative to best available utility.
    """
    out = dict(row)
    value_i = float(cand_i.get("estimated_value_if_allocate_next", out.get("pair_value_i", 0.0)))
    value_j = float(cand_j.get("estimated_value_if_allocate_next", out.get("pair_value_j", 0.0)))
    outside = float(out.get("outside_option_value_estimate", cand_i.get("outside_option_value", cand_j.get("outside_option_value", 0.0))))
    best_available = max(float(state_best_value), float(outside)) if use_outside_option else float(state_best_value)

    regret_i = max(0.0, best_available - value_i)
    regret_j = max(0.0, best_available - value_j)
    better_regret = min(regret_i, regret_j)
    worse_regret = max(regret_i, regret_j)
    regret_gap = abs(regret_i - regret_j)
    regret_gap_rel = regret_gap / max(abs(best_available), abs(value_i), abs(value_j), 1e-6)

    # Prefer lower-regret branch (equivalent direction to higher value under fixed best_available).
    prefer_i = regret_i <= regret_j
    out["label"] = 1 if prefer_i else 0
    out["preference"] = int(out["label"])
    out["margin"] = float(regret_j - regret_i)
    out["margin_abs"] = abs(float(out["margin"]))
    out["relative_margin"] = float(regret_gap_rel)
    out["near_tie_flag"] = bool(regret_gap <= float(near_tie_margin))

    out["allocation_regret_target_enabled"] = True
    out["allocation_regret_target_source"] = "best_available_regret_v1"
    out["allocation_regret_use_outside_option"] = bool(use_outside_option)
    out["allocation_regret_best_value_in_state"] = float(state_best_value)
    out["allocation_regret_outside_option_value"] = float(outside)
    out["allocation_regret_best_available_value"] = float(best_available)
    out["allocation_regret_i"] = float(regret_i)
    out["allocation_regret_j"] = float(regret_j)
    out["allocation_regret_best_pair"] = float(better_regret)
    out["allocation_regret_worse_pair"] = float(worse_regret)
    out["allocation_regret_gap"] = float(regret_gap)
    out["allocation_regret_gap_relative"] = float(regret_gap_rel)

    # Explicit consequence-aware supervision magnitude (cost of wrong allocation choice).
    # Keep this bounded and compositional with existing pairwise weighting path.
    regret_cost_weight = 1.0 + min(2.0, worse_regret / max(abs(best_available), 1e-6))
    out["allocation_regret_cost_weight"] = float(regret_cost_weight)
    out["supervision_reliability_weight"] = float(out.get("supervision_reliability_weight", 1.0)) * float(regret_cost_weight)
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
    state_best_value_map: dict[str, float] = {}
    for sid, cand_rows in state_to_cands.items():
        if not cand_rows:
            state_best_value_map[sid] = 0.0
            continue
        state_best_value_map[sid] = max(float(r.get("estimated_value_if_allocate_next", 0.0)) for r in cand_rows)
    state_branch_index_map = _build_state_branch_index(candidates)

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
            "multistep_utility_lambda": args.multistep_utility_lambda,
            "response_curve_max_horizon": int(args.response_curve_max_horizon),
            "response_curve_score_w1": float(args.response_curve_score_w1),
            "response_curve_score_w2": float(args.response_curve_score_w2),
            "response_curve_score_w3": float(args.response_curve_score_w3),
            "rank_instability_discount_gamma": float(args.rank_instability_discount_gamma),
            "rank_instability_margin_threshold": float(args.rank_instability_margin_threshold),
            "rank_instability_min_disagreement_count": int(args.rank_instability_min_disagreement_count),
        },
        "regimes": {},
    }

    state_rank_instability: dict[str, dict[str, Any]] = {}
    for sid, rows in state_to_cands.items():
        state_rank_instability[sid] = _statewise_rank_instability_signals(
            rows,
            state_id=sid,
            branch_index_map=state_branch_index_map,
            utility_lambda=float(args.multistep_utility_lambda),
            discount_gamma=float(args.rank_instability_discount_gamma),
            response_curve_max_horizon=int(args.response_curve_max_horizon),
            response_curve_score_weights=(
                float(args.response_curve_score_w1),
                float(args.response_curve_score_w2),
                float(args.response_curve_score_w3),
            ),
            margin_threshold=float(args.rank_instability_margin_threshold),
            min_disagreement_count=int(args.rank_instability_min_disagreement_count),
        )

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
                    elif strat == "allocation_regret_target":
                        keep = True
                    elif strat == "allocation_regret_target_no_outside":
                        keep = True
                    elif strat in {"multistep_branch_utility_target_k1", "multistep_branch_utility_target_k2", "multistep_branch_utility_target_k3"}:
                        keep = True
                    elif strat == "compute_response_curve_target_h123":
                        keep = True
                    elif strat == "rank_instability_target_v1":
                        keep = True
                    elif _parse_discounted_gamma_from_strategy(strat) is not None:
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
                        if strat in {"allocation_regret_target", "allocation_regret_target_no_outside"}:
                            annotated = _annotate_allocation_regret_target(
                                annotated,
                                cand_i=cand_map[(sid, str(annotated["branch_i"]))],
                                cand_j=cand_map[(sid, str(annotated["branch_j"]))],
                                state_best_value=float(state_best_value_map.get(sid, 0.0)),
                                use_outside_option=(strat == "allocation_regret_target"),
                                near_tie_margin=float(args.near_tie_margin),
                            )
                        if strat in {"multistep_branch_utility_target_k1", "multistep_branch_utility_target_k2", "multistep_branch_utility_target_k3"}:
                            horizon_k = int(strat.rsplit("_k", 1)[1])
                            ci = cand_map[(sid, str(annotated["branch_i"]))]
                            cj = cand_map[(sid, str(annotated["branch_j"]))]
                            ui = _multistep_utility_target_for_candidate(
                                ci,
                                state_id=sid,
                                branch_id=str(annotated["branch_i"]),
                                branch_index_map=state_branch_index_map,
                                horizon_k=horizon_k,
                                utility_lambda=float(args.multistep_utility_lambda),
                            )
                            uj = _multistep_utility_target_for_candidate(
                                cj,
                                state_id=sid,
                                branch_id=str(annotated["branch_j"]),
                                branch_index_map=state_branch_index_map,
                                horizon_k=horizon_k,
                                utility_lambda=float(args.multistep_utility_lambda),
                            )
                            multistep_margin = float(ui["multistep_branch_utility_target"] - uj["multistep_branch_utility_target"])
                            annotated["label"] = 1 if multistep_margin >= 0.0 else 0
                            annotated["preference"] = int(annotated["label"])
                            annotated["margin"] = float(multistep_margin)
                            annotated["margin_abs"] = abs(float(multistep_margin))
                            denom = max(
                                abs(float(ui["multistep_branch_utility_target"])),
                                abs(float(uj["multistep_branch_utility_target"])),
                                1e-6,
                            )
                            annotated["relative_margin"] = abs(float(multistep_margin)) / float(denom)
                            annotated["near_tie_flag"] = bool(abs(float(multistep_margin)) <= float(args.near_tie_margin))
                            annotated["label_source"] = "multistep_branch_utility_target"
                            annotated["multistep_target_horizon_k"] = float(horizon_k)
                            annotated["multistep_target_utility_lambda"] = float(args.multistep_utility_lambda)
                            annotated["pair_multistep_utility_i"] = float(ui["multistep_branch_utility_target"])
                            annotated["pair_multistep_utility_j"] = float(uj["multistep_branch_utility_target"])
                            annotated["pair_multistep_utility_gap"] = float(abs(multistep_margin))
                            annotated["pair_multistep_target_source"] = "best_followup_allocation_self_mass_proxy_v1"
                        if strat == "compute_response_curve_target_h123":
                            ci = cand_map[(sid, str(annotated["branch_i"]))]
                            cj = cand_map[(sid, str(annotated["branch_j"]))]
                            ui = _compute_response_curve_target_for_candidate(
                                ci,
                                state_id=sid,
                                branch_id=str(annotated["branch_i"]),
                                branch_index_map=state_branch_index_map,
                                utility_lambda=float(args.multistep_utility_lambda),
                                max_horizon=int(args.response_curve_max_horizon),
                                score_weights=(
                                    float(args.response_curve_score_w1),
                                    float(args.response_curve_score_w2),
                                    float(args.response_curve_score_w3),
                                ),
                            )
                            uj = _compute_response_curve_target_for_candidate(
                                cj,
                                state_id=sid,
                                branch_id=str(annotated["branch_j"]),
                                branch_index_map=state_branch_index_map,
                                utility_lambda=float(args.multistep_utility_lambda),
                                max_horizon=int(args.response_curve_max_horizon),
                                score_weights=(
                                    float(args.response_curve_score_w1),
                                    float(args.response_curve_score_w2),
                                    float(args.response_curve_score_w3),
                                ),
                            )
                            curve_score_margin = float(ui["compute_response_curve_decision_scalar"] - uj["compute_response_curve_decision_scalar"])
                            annotated["label"] = 1 if curve_score_margin >= 0.0 else 0
                            annotated["preference"] = int(annotated["label"])
                            annotated["margin"] = float(curve_score_margin)
                            annotated["margin_abs"] = abs(float(curve_score_margin))
                            denom = max(
                                abs(float(ui["compute_response_curve_decision_scalar"])),
                                abs(float(uj["compute_response_curve_decision_scalar"])),
                                1e-6,
                            )
                            annotated["relative_margin"] = abs(float(curve_score_margin)) / float(denom)
                            annotated["near_tie_flag"] = bool(abs(float(curve_score_margin)) <= float(args.near_tie_margin))
                            annotated["label_source"] = "compute_response_curve_target"
                            annotated["compute_response_curve_target_version"] = str(ui.get("compute_response_curve_target_version", "compute_response_curve_target_v1"))
                            annotated["pair_curve_i_h1"] = float(ui["compute_response_curve_h1"])
                            annotated["pair_curve_i_h2"] = float(ui["compute_response_curve_h2"])
                            annotated["pair_curve_i_h3"] = float(ui["compute_response_curve_h3"])
                            annotated["pair_curve_j_h1"] = float(uj["compute_response_curve_h1"])
                            annotated["pair_curve_j_h2"] = float(uj["compute_response_curve_h2"])
                            annotated["pair_curve_j_h3"] = float(uj["compute_response_curve_h3"])
                            annotated["pair_curve_scalar_i"] = float(ui["compute_response_curve_decision_scalar"])
                            annotated["pair_curve_scalar_j"] = float(uj["compute_response_curve_decision_scalar"])
                            annotated["pair_curve_scalar_gap"] = abs(float(curve_score_margin))
                            annotated["pair_curve_marginal_gap_m1"] = float(ui["compute_response_curve_marginal_m1"] - uj["compute_response_curve_marginal_m1"])
                            annotated["pair_curve_marginal_gap_m2"] = float(ui["compute_response_curve_marginal_m2"] - uj["compute_response_curve_marginal_m2"])
                            annotated["pair_curve_marginal_gap_m3"] = float(ui["compute_response_curve_marginal_m3"] - uj["compute_response_curve_marginal_m3"])
                        if strat == "rank_instability_target_v1":
                            rank_meta = state_rank_instability.get(sid, {})
                            pair_signals = rank_meta.get("rank_instability_pair_orientations", {})
                            ori_key = tuple(sorted([str(annotated["branch_i"]), str(annotated["branch_j"])]))
                            ori = pair_signals.get(ori_key, {})
                            if str(annotated["branch_i"]) <= str(annotated["branch_j"]):
                                one_step_pref = int(ori.get("one_step", int(annotated.get("label", 0))))
                                multistep_pref = int(ori.get("multistep_k3", one_step_pref))
                                discounted_pref = int(ori.get("discounted_gamma", one_step_pref))
                                curve_pref = int(ori.get("curve_scalar", one_step_pref))
                            else:
                                one_step_pref = 1 - int(ori.get("one_step", 1 - int(annotated.get("label", 0))))
                                multistep_pref = 1 - int(ori.get("multistep_k3", 1 - one_step_pref))
                                discounted_pref = 1 - int(ori.get("discounted_gamma", 1 - one_step_pref))
                                curve_pref = 1 - int(ori.get("curve_scalar", 1 - one_step_pref))
                            disagreement_count = int(
                                int(one_step_pref != multistep_pref)
                                + int(one_step_pref != discounted_pref)
                                + int(one_step_pref != curve_pref)
                            )
                            annotated["label"] = int(multistep_pref)
                            annotated["preference"] = int(multistep_pref)
                            annotated["label_source"] = "rank_instability_target_multistep_k3_anchor"
                            annotated["rank_instability_target_version"] = "rank_instability_target_v1"
                            annotated["rank_instability_top1_by_signal"] = rank_meta.get("top1_by_signal", {})
                            annotated["rank_instability_top1_margin_by_signal"] = rank_meta.get("top1_margin_by_signal", {})
                            annotated["rank_instability_state_label"] = bool(rank_meta.get("rank_instability_state_label", False))
                            annotated["rank_instability_state_score"] = float(rank_meta.get("rank_instability_state_score", 0.0))
                            annotated["rank_instability_top1_disagreement_count"] = int(rank_meta.get("rank_instability_top1_disagreement_count", 0))
                            annotated["rank_instability_min_top1_margin_abs"] = float(rank_meta.get("rank_instability_min_top1_margin_abs", 0.0))
                            annotated["rank_instability_pair_disagreement_count"] = int(disagreement_count)
                            annotated["rank_instability_pair_label"] = bool(
                                disagreement_count >= 2
                                and float(annotated.get("margin_abs", 0.0)) <= float(args.rank_instability_margin_threshold)
                            )
                            annotated["rank_instability_pair_score"] = float(min(1.0, disagreement_count / 3.0))
                            annotated["rank_instability_pair_pref_one_step"] = int(one_step_pref)
                            annotated["rank_instability_pair_pref_multistep_k3"] = int(multistep_pref)
                            annotated["rank_instability_pair_pref_discounted"] = int(discounted_pref)
                            annotated["rank_instability_pair_pref_curve"] = int(curve_pref)
                            annotated["rank_instability_discount_gamma"] = float(args.rank_instability_discount_gamma)
                            annotated["rank_instability_margin_threshold"] = float(args.rank_instability_margin_threshold)
                            annotated["rank_instability_min_disagreement_count"] = int(args.rank_instability_min_disagreement_count)
                        gamma = _parse_discounted_gamma_from_strategy(strat)
                        if gamma is not None:
                            ci = cand_map[(sid, str(annotated["branch_i"]))]
                            cj = cand_map[(sid, str(annotated["branch_j"]))]
                            ui = _discounted_multistep_utility_target_for_candidate(
                                ci,
                                state_id=sid,
                                branch_id=str(annotated["branch_i"]),
                                branch_index_map=state_branch_index_map,
                                utility_lambda=float(args.multistep_utility_lambda),
                                discount_gamma=float(gamma),
                                max_horizon=3,
                            )
                            uj = _discounted_multistep_utility_target_for_candidate(
                                cj,
                                state_id=sid,
                                branch_id=str(annotated["branch_j"]),
                                branch_index_map=state_branch_index_map,
                                utility_lambda=float(args.multistep_utility_lambda),
                                discount_gamma=float(gamma),
                                max_horizon=3,
                            )
                            discounted_margin = float(ui["multistep_branch_utility_target"] - uj["multistep_branch_utility_target"])
                            annotated["label"] = 1 if discounted_margin >= 0.0 else 0
                            annotated["preference"] = int(annotated["label"])
                            annotated["margin"] = float(discounted_margin)
                            annotated["margin_abs"] = abs(float(discounted_margin))
                            denom = max(
                                abs(float(ui["multistep_branch_utility_target"])),
                                abs(float(uj["multistep_branch_utility_target"])),
                                1e-6,
                            )
                            annotated["relative_margin"] = abs(float(discounted_margin)) / float(denom)
                            annotated["near_tie_flag"] = bool(abs(float(discounted_margin)) <= float(args.near_tie_margin))
                            annotated["label_source"] = "discounted_multistep_branch_utility_target"
                            annotated["multistep_target_horizon_k"] = float(ui.get("multistep_target_horizon_k", 3.0))
                            annotated["multistep_target_discount_gamma"] = float(gamma)
                            annotated["multistep_target_utility_lambda"] = float(args.multistep_utility_lambda)
                            annotated["pair_multistep_utility_i"] = float(ui["multistep_branch_utility_target"])
                            annotated["pair_multistep_utility_j"] = float(uj["multistep_branch_utility_target"])
                            annotated["pair_multistep_utility_gap"] = float(abs(discounted_margin))
                            annotated["pair_multistep_target_source"] = "discounted_multistep_branch_utility_target_v1"
                        kept.append(annotated)

        if strat in {"opportunity_intensity_weighted", "opportunity_intensity_weighted_no_outside_norm"}:
            kept = _apply_opportunity_weight_normalization(
                kept,
                final_min=float(args.opportunity_intensity_final_min),
                final_max=float(args.opportunity_intensity_final_max),
            )

        regime_candidates = [dict(c) for c in candidates]
        if strat in {"multistep_branch_utility_target_k1", "multistep_branch_utility_target_k2", "multistep_branch_utility_target_k3"}:
            horizon_k = int(strat.rsplit("_k", 1)[1])
            for rc in regime_candidates:
                sid = str(rc.get("state_id", ""))
                bid = str(rc.get("branch_id", ""))
                rc.update(
                    _multistep_utility_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        horizon_k=horizon_k,
                        utility_lambda=float(args.multistep_utility_lambda),
                    )
                )
        gamma = _parse_discounted_gamma_from_strategy(strat)
        if gamma is not None:
            for rc in regime_candidates:
                sid = str(rc.get("state_id", ""))
                bid = str(rc.get("branch_id", ""))
                rc.update(
                    _discounted_multistep_utility_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        utility_lambda=float(args.multistep_utility_lambda),
                        discount_gamma=float(gamma),
                        max_horizon=3,
                    )
                )
        if strat == "compute_response_curve_target_h123":
            for rc in regime_candidates:
                sid = str(rc.get("state_id", ""))
                bid = str(rc.get("branch_id", ""))
                rc.update(
                    _compute_response_curve_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        utility_lambda=float(args.multistep_utility_lambda),
                        max_horizon=int(args.response_curve_max_horizon),
                        score_weights=(
                            float(args.response_curve_score_w1),
                            float(args.response_curve_score_w2),
                            float(args.response_curve_score_w3),
                        ),
                    )
                )
        if strat == "rank_instability_target_v1":
            for rc in regime_candidates:
                sid = str(rc.get("state_id", ""))
                bid = str(rc.get("branch_id", ""))
                rc.update(
                    _multistep_utility_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        horizon_k=3,
                        utility_lambda=float(args.multistep_utility_lambda),
                    )
                )
                rc.update(
                    _discounted_multistep_utility_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        utility_lambda=float(args.multistep_utility_lambda),
                        discount_gamma=float(args.rank_instability_discount_gamma),
                        max_horizon=3,
                    )
                )
                rc.update(
                    _compute_response_curve_target_for_candidate(
                        rc,
                        state_id=sid,
                        branch_id=bid,
                        branch_index_map=state_branch_index_map,
                        utility_lambda=float(args.multistep_utility_lambda),
                        max_horizon=int(args.response_curve_max_horizon),
                        score_weights=(
                            float(args.response_curve_score_w1),
                            float(args.response_curve_score_w2),
                            float(args.response_curve_score_w3),
                        ),
                    )
                )
                rank_meta = state_rank_instability.get(sid, {})
                rc["rank_instability_target_version"] = "rank_instability_target_v1"
                rc["rank_instability_state_label"] = bool(rank_meta.get("rank_instability_state_label", False))
                rc["rank_instability_state_score"] = float(rank_meta.get("rank_instability_state_score", 0.0))
                rc["rank_instability_top1_disagreement_count"] = int(rank_meta.get("rank_instability_top1_disagreement_count", 0))
                rc["rank_instability_unique_top1_count"] = int(rank_meta.get("rank_instability_unique_top1_count", 1))
                rc["rank_instability_min_top1_margin_abs"] = float(rank_meta.get("rank_instability_min_top1_margin_abs", 0.0))
                rc["rank_instability_top1_by_signal"] = rank_meta.get("top1_by_signal", {})
                rc["rank_instability_top1_margin_by_signal"] = rank_meta.get("top1_margin_by_signal", {})
                rc["rank_instability_top1_contains_branch"] = bool(
                    bid in set(str(v) for v in rank_meta.get("top1_by_signal", {}).values())
                )
                rc["rank_instability_discount_gamma"] = float(args.rank_instability_discount_gamma)
                rc["rank_instability_margin_threshold"] = float(args.rank_instability_margin_threshold)
                rc["rank_instability_min_disagreement_count"] = int(args.rank_instability_min_disagreement_count)
        out_dir = out_root / f"regime_{strat}"
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out_dir / "candidate_labels.jsonl", regime_candidates)
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
            "allocation_regret_gap_mean": (
                sum(float(r.get("allocation_regret_gap", 0.0)) for r in kept) / max(1, len(kept))
            ),
            "allocation_regret_gap_near_tie_mean": (
                sum(float(r.get("allocation_regret_gap", 0.0)) for r in kept if bool(r.get("near_tie_flag", False)))
                / max(1, sum(1 for r in kept if bool(r.get("near_tie_flag", False))))
            ),
            "allocation_regret_gap_non_near_tie_mean": (
                sum(float(r.get("allocation_regret_gap", 0.0)) for r in kept if (not bool(r.get("near_tie_flag", False))))
                / max(1, sum(1 for r in kept if (not bool(r.get("near_tie_flag", False)))))
            ),
            "allocation_regret_worse_pair_mean": (
                sum(float(r.get("allocation_regret_worse_pair", 0.0)) for r in kept) / max(1, len(kept))
            ),
            "allocation_regret_worse_pair_near_tie_mean": (
                sum(float(r.get("allocation_regret_worse_pair", 0.0)) for r in kept if bool(r.get("near_tie_flag", False)))
                / max(1, sum(1 for r in kept if bool(r.get("near_tie_flag", False))))
            ),
            "allocation_regret_worse_pair_non_near_tie_mean": (
                sum(float(r.get("allocation_regret_worse_pair", 0.0)) for r in kept if (not bool(r.get("near_tie_flag", False))))
                / max(1, sum(1 for r in kept if (not bool(r.get("near_tie_flag", False)))))
            ),
            "allocation_regret_cost_weight_mean": (
                sum(float(r.get("allocation_regret_cost_weight", 1.0)) for r in kept) / max(1, len(kept))
            ),
            "pair_multistep_utility_gap_mean": (
                sum(float(r.get("pair_multistep_utility_gap", 0.0)) for r in kept) / max(1, len(kept))
            ),
            "pair_multistep_utility_gap_near_tie_mean": (
                sum(float(r.get("pair_multistep_utility_gap", 0.0)) for r in kept if bool(r.get("near_tie_flag", False)))
                / max(1, sum(1 for r in kept if bool(r.get("near_tie_flag", False))))
            ),
            "pair_curve_scalar_gap_mean": (
                sum(float(r.get("pair_curve_scalar_gap", 0.0)) for r in kept) / max(1, len(kept))
            ),
            "pair_curve_scalar_gap_near_tie_mean": (
                sum(float(r.get("pair_curve_scalar_gap", 0.0)) for r in kept if bool(r.get("near_tie_flag", False)))
                / max(1, sum(1 for r in kept if bool(r.get("near_tie_flag", False))))
            ),
            "rank_instability_state_label_rate": (
                sum(1 for r in kept if bool(r.get("rank_instability_state_label", False))) / max(1, len(kept))
            ),
            "rank_instability_pair_label_rate": (
                sum(1 for r in kept if bool(r.get("rank_instability_pair_label", False))) / max(1, len(kept))
            ),
            "rank_instability_pair_disagreement_count_mean": (
                sum(float(r.get("rank_instability_pair_disagreement_count", 0.0)) for r in kept) / max(1, len(kept))
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
