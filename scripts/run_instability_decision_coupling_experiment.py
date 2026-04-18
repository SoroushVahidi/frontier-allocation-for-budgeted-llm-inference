#!/usr/bin/env python3
"""Bounded instability-to-decision coupling experiment for fixed-budget branch allocation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import pstdev
from typing import Any, Callable

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    load_label_artifacts,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_int_csv(text: str) -> list[int]:
    vals = [int(x.strip()) for x in str(text).split(",") if x.strip()]
    if not vals:
        raise ValueError("Expected at least one seed")
    return vals


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _fit_linear_pointwise(candidates: list[dict[str, Any]], target_field: str, seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train), "target_field": target_field}
    x = np.asarray([r["x"] for r in train], dtype=float)
    y = np.asarray([float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in train], dtype=float)
    if float(np.std(y)) <= 1e-12:
        return {"status": "degenerate_target", "training_rows": len(train), "target_field": target_field}
    model = Ridge(alpha=1.0, random_state=int(seed))
    model.fit(x, y)
    return {
        "status": "ok",
        "target_field": target_field,
        "weights": np.asarray(model.coef_, dtype=float).tolist(),
        "intercept": float(model.intercept_),
        "training_rows": len(train),
    }


def _linear_scorer(model: dict[str, Any]) -> Callable[[list[float]], float]:
    w = np.asarray(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    return lambda x: float(np.dot(w, np.asarray(x, dtype=float)) + b)


def _fit_instability_head(pair_rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in pair_rows if str(r.get("split")) == "train"]
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    for r in train:
        x_rows.append(
            [
                float(r.get("margin_abs", 0.0)),
                float(r.get("relative_margin", 0.0)),
                float(r.get("pair_uncertainty_std_mean", 0.0)),
                float(r.get("rank_instability_pair_disagreement_count", 0.0)),
                float(r.get("rank_instability_state_score", 0.0)),
                1.0 if bool(r.get("near_tie_flag", False)) else 0.0,
                1.0 if str(r.get("pair_type", "")) == "adjacent_rank" else 0.0,
            ]
        )
        y_rows.append(1 if bool(r.get("rank_instability_pair_label", False)) else 0)
    if len(x_rows) < 16 or len(set(y_rows)) < 2:
        return {"status": "insufficient_or_single_class", "training_rows": len(x_rows)}

    x = np.asarray(x_rows, dtype=float)
    y = np.asarray(y_rows, dtype=int)
    m = LogisticRegression(max_iter=500, random_state=int(seed), class_weight="balanced")
    m.fit(x, y)
    return {
        "status": "ok",
        "weights": np.asarray(m.coef_, dtype=float).reshape(-1).tolist(),
        "intercept": float(np.asarray(m.intercept_, dtype=float).reshape(-1)[0]),
        "training_rows": len(x_rows),
        "positive_rate": float(np.mean(y)),
    }


def _instability_prob(model: dict[str, Any], row: dict[str, Any]) -> float:
    w = np.asarray(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    x = np.asarray(
        [
            float(row.get("margin_abs", 0.0)),
            float(row.get("relative_margin", 0.0)),
            float(row.get("pair_uncertainty_std_mean", 0.0)),
            float(row.get("rank_instability_pair_disagreement_count", 0.0)),
            float(row.get("rank_instability_state_score", 0.0)),
            1.0 if bool(row.get("near_tie_flag", False)) else 0.0,
            1.0 if str(row.get("pair_type", "")) == "adjacent_rank" else 0.0,
        ],
        dtype=float,
    )
    z = float(np.dot(w, x) + b)
    return float(1.0 / (1.0 + np.exp(-z)))


def _build_state_tables(candidates: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str], dict[str, dict[str, dict[str, float | str]]]]:
    test_by_state: dict[str, list[dict[str, Any]]] = {}
    oracle_best: dict[str, str] = {}
    feature_table: dict[str, dict[str, dict[str, float | str]]] = {}
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        bid = str(r.get("branch_id", ""))
        test_by_state.setdefault(sid, []).append(r)
        feature_table.setdefault(sid, {})[bid] = {
            "outside_gap": float(r.get("branch_vs_outside_gap", 0.0)),
            "multistep_delta": float(r.get("multistep_branch_utility_delta_vs_onestep", 0.0)),
            "one_step": float(r.get("estimated_value_if_allocate_next", 0.0)),
            "state_instability_score": float(r.get("rank_instability_state_score", 0.0)),
            "state_instability_label": 1.0 if bool(r.get("rank_instability_state_label", False)) else 0.0,
        }

    for sid, rows in test_by_state.items():
        if not rows:
            continue
        best = max(rows, key=lambda rr: float(rr.get("estimated_value_if_allocate_next", 0.0)))
        oracle_best[sid] = str(best.get("branch_id", ""))
    return test_by_state, oracle_best, feature_table


def _state_flags(pair_rows: list[dict[str, Any]]) -> tuple[dict[str, bool], dict[str, bool]]:
    near_tie: dict[str, bool] = {}
    adjacent: dict[str, bool] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        near_tie[sid] = bool(near_tie.get(sid, False) or bool(r.get("near_tie_flag", False)))
        adjacent[sid] = bool(adjacent.get(sid, False) or str(r.get("pair_type", "")) == "adjacent_rank")
    return near_tie, adjacent


def _pair_lookup(pair_rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        bi = str(r.get("branch_i", ""))
        bj = str(r.get("branch_j", ""))
        out[(sid, min(bi, bj), max(bi, bj))] = r
    return out


def _top2_pair_row(sid: str, top_a: str, top_b: str, lookup: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any] | None:
    return lookup.get((sid, min(top_a, top_b), max(top_a, top_b)))


def _policy_decision(
    *,
    policy: str,
    sid: str,
    ranked: list[dict[str, Any]],
    top2_row: dict[str, Any] | None,
    instability_prob: float,
    near_tie: bool,
    adjacent: bool,
    cfg: argparse.Namespace,
) -> tuple[str, bool, list[str], list[dict[str, Any]]]:
    reasons: list[str] = []
    adjusted = [dict(x) for x in ranked]

    if not ranked:
        return "", True, ["empty_state"], adjusted

    top = adjusted[0]
    second = adjusted[1] if len(adjusted) > 1 else adjusted[0]
    gap_raw = float(top["raw_score"] - second["raw_score"])
    outside_top = float(top.get("outside_gap", 0.0))

    if policy == "multistep_k3_current":
        return str(top["branch_id"]), False, ["always_accept_top_multistep"], adjusted

    if policy == "rank_instability_aware_current":
        state_instable = bool(top.get("state_instability_label", False))
        defer = bool((instability_prob >= float(cfg.current_instability_threshold) or state_instable) and gap_raw <= (1.5 * float(cfg.current_margin_threshold)))
        if defer:
            reasons.append("current_policy_defer_instability_and_small_gap")
        return str(top["branch_id"]), defer, reasons or ["current_policy_accept"], adjusted

    if policy == "defer_on_instability":
        defer = bool(instability_prob >= float(cfg.defer_instability_threshold) and gap_raw <= float(cfg.defer_margin_threshold))
        if defer:
            reasons.append("high_instability_small_margin")
        return str(top["branch_id"]), defer, reasons or ["accept_top"], adjusted

    if policy == "instability_penalized_top_score":
        for item in adjusted:
            outside_weak = max(0.0, float(cfg.penalty_outside_weak_floor) - float(item.get("outside_gap", 0.0)))
            state_term = float(item.get("state_instability_score", 0.0))
            item["adjusted_score"] = float(item["raw_score"] - float(cfg.penalty_weight) * instability_prob * (outside_weak + float(cfg.penalty_state_score_weight) * state_term))
        adjusted.sort(key=lambda rr: rr.get("adjusted_score", rr["raw_score"]), reverse=True)
        chosen = adjusted[0]
        runner = adjusted[1] if len(adjusted) > 1 else adjusted[0]
        adjusted_gap = float(chosen.get("adjusted_score", chosen["raw_score"]) - runner.get("adjusted_score", runner["raw_score"]))
        defer = bool(instability_prob >= float(cfg.penalty_defer_instability_threshold) and adjusted_gap <= float(cfg.penalty_defer_adjusted_margin_threshold))
        if defer:
            reasons.append("penalized_top_small_adjusted_gap")
        if str(chosen["branch_id"]) != str(top["branch_id"]):
            reasons.append("top_changed_by_instability_penalty")
        return str(chosen["branch_id"]), defer, reasons or ["accept_penalized_top"], adjusted

    if policy == "instability_outside_option_gate":
        strong_outside = outside_top >= float(cfg.gate_outside_gap_threshold)
        low_instability = instability_prob <= float(cfg.gate_instability_threshold)
        defer = bool(not (low_instability or strong_outside) and gap_raw <= float(cfg.gate_margin_threshold))
        if defer:
            reasons.append("gate_blocked_high_instability_weak_outside")
        return str(top["branch_id"]), defer, reasons or ["gate_accept_top"], adjusted

    if policy == "selective_hard_case_abstention":
        hard = bool(near_tie or adjacent)
        require_strong = bool(hard and instability_prob >= float(cfg.hard_instability_threshold))
        if require_strong:
            strong_rank = gap_raw >= float(cfg.hard_margin_threshold)
            strong_outside = outside_top >= float(cfg.hard_outside_threshold)
            defer = not (strong_rank and strong_outside)
            if defer:
                reasons.append("hard_case_requires_rank_and_outside")
            else:
                reasons.append("hard_case_passed_rank_and_outside")
            return str(top["branch_id"]), defer, reasons, adjusted
        return str(top["branch_id"]), False, ["non_hard_or_low_instability_accept"], adjusted

    return str(top["branch_id"]), False, ["unknown_policy_default_accept"], adjusted


def _evaluate(
    *,
    rows: list[dict[str, Any]],
    oracle_best: dict[str, str],
    near_tie_flags: dict[str, bool],
    adjacent_flags: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    total = len(rows)
    accepted = [r for r in rows if not bool(r.get("defer", False))]

    forced_correct = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in rows)
    accepted_correct = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in accepted)

    def _slice_acc(slice_rows: list[dict[str, Any]]) -> float:
        if not slice_rows:
            return 0.0
        corr = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in slice_rows)
        return float(corr / len(slice_rows))

    near_acc_rows = [r for r in accepted if bool(near_tie_flags.get(str(r.get("state_id", "")), False))]
    adj_acc_rows = [r for r in accepted if bool(adjacent_flags.get(str(r.get("state_id", "")), False))]
    strict_acc_rows = [
        r
        for r in accepted
        if bool(near_tie_flags.get(str(r.get("state_id", "")), False)) and bool(adjacent_flags.get(str(r.get("state_id", "")), False))
    ]

    wrong_accepted = [r for r in accepted if str(r.get("choice", "")) != str(oracle_best.get(str(r.get("state_id", "")), ""))]
    fragile_overconfident_wrong = [
        r
        for r in wrong_accepted
        if float(r.get("score_gap_top2", 0.0)) >= 0.08 and float(r.get("instability_prob_top2", 0.0)) <= 0.35
    ]

    delayed_payoff_wrong = [
        r
        for r in wrong_accepted
        if bool(r.get("delayed_payoff_overvaluation_with_outside_option_miss", False))
    ]

    deferred = [r for r in rows if bool(r.get("defer", False))]
    easy_states = [r for r in rows if not bool(r.get("is_near_tie", False)) and not bool(r.get("is_adjacent", False))]
    easy_deferred = [r for r in deferred if not bool(r.get("is_near_tie", False)) and not bool(r.get("is_adjacent", False))]

    metrics = {
        "forced_accuracy": float(forced_correct / total) if total else 0.0,
        "accepted_accuracy": float(accepted_correct / len(accepted)) if accepted else 0.0,
        "coverage": float(len(accepted) / total) if total else 0.0,
        "defer_rate": float(1.0 - (len(accepted) / total)) if total else 0.0,
        "states": total,
        "accepted_states": len(accepted),
        "deferred_states": len(deferred),
        "near_tie_accepted_accuracy": _slice_acc(near_acc_rows),
        "near_tie_accepted_n": len(near_acc_rows),
        "adjacent_rank_accepted_accuracy": _slice_acc(adj_acc_rows),
        "adjacent_rank_accepted_n": len(adj_acc_rows),
        "strict_hard_slice_accepted_accuracy": _slice_acc(strict_acc_rows),
        "strict_hard_slice_accepted_n": len(strict_acc_rows),
        "failure_states": len(wrong_accepted),
        "fragile_overconfident_wrong_accepts": len(fragile_overconfident_wrong),
        "fragile_overconfident_wrong_rate_on_failures": float(len(fragile_overconfident_wrong) / len(wrong_accepted)) if wrong_accepted else 0.0,
        "delayed_payoff_overvaluation_failures": len(delayed_payoff_wrong),
        "easy_state_count": len(easy_states),
        "easy_state_defer_count": len(easy_deferred),
        "easy_state_defer_rate": float(len(easy_deferred) / len(easy_states)) if easy_states else 0.0,
        "spillover_non_hard_defer_count": len(easy_deferred),
        "spillover_non_hard_defer_rate": float(len(easy_deferred) / len(rows)) if rows else 0.0,
    }

    reason_counts: dict[str, int] = {}
    for r in rows:
        for reason in r.get("defer_reasons", []):
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1

    diagnostics = {
        "reason_counts": reason_counts,
        "wrong_accepted_examples": wrong_accepted[:100],
        "deferred_examples": deferred[:100],
    }
    return metrics, diagnostics


def _aggregate_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "seeds": len(rows),
        "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
        "accepted_accuracy_std": float(pstdev([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows])) if len(rows) > 1 else 0.0,
        "forced_accuracy_mean": _mean([float(r["metrics"].get("forced_accuracy", 0.0)) for r in rows]),
        "coverage_mean": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
        "defer_rate_mean": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
        "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
        "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
        "strict_hard_slice_accepted_accuracy_mean": _mean([float(r["metrics"].get("strict_hard_slice_accepted_accuracy", 0.0)) for r in rows]),
        "fragile_overconfident_wrong_accepts_mean": _mean([float(r["metrics"].get("fragile_overconfident_wrong_accepts", 0.0)) for r in rows]),
        "fragile_overconfident_wrong_rate_on_failures_mean": _mean([float(r["metrics"].get("fragile_overconfident_wrong_rate_on_failures", 0.0)) for r in rows]),
        "delayed_payoff_overvaluation_failures_mean": _mean([float(r["metrics"].get("delayed_payoff_overvaluation_failures", 0.0)) for r in rows]),
        "easy_state_defer_rate_mean": _mean([float(r["metrics"].get("easy_state_defer_rate", 0.0)) for r in rows]),
        "spillover_non_hard_defer_rate_mean": _mean([float(r["metrics"].get("spillover_non_hard_defer_rate", 0.0)) for r in rows]),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded instability-to-decision coupling experiment")
    p.add_argument("--targets-root", default="outputs/branch_label_bruteforce_targets/rank_instability_target_20260418")
    p.add_argument("--run-id", default="instability_decision_coupling_eval_20260418")
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--multistep-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--discounted-regime", default="discounted_multistep_branch_utility_target_gamma080")
    p.add_argument("--curve-regime", default="compute_response_curve_target_h123")
    p.add_argument("--rank-instability-regime", default="rank_instability_target_v1")

    p.add_argument("--current-instability-threshold", type=float, default=0.35)
    p.add_argument("--current-margin-threshold", type=float, default=0.10)

    p.add_argument("--defer-instability-threshold", type=float, default=0.55)
    p.add_argument("--defer-margin-threshold", type=float, default=0.08)

    p.add_argument("--penalty-weight", type=float, default=0.40)
    p.add_argument("--penalty-state-score-weight", type=float, default=0.50)
    p.add_argument("--penalty-outside-weak-floor", type=float, default=0.05)
    p.add_argument("--penalty-defer-instability-threshold", type=float, default=0.70)
    p.add_argument("--penalty-defer-adjusted-margin-threshold", type=float, default=0.03)

    p.add_argument("--gate-instability-threshold", type=float, default=0.45)
    p.add_argument("--gate-outside-gap-threshold", type=float, default=0.04)
    p.add_argument("--gate-margin-threshold", type=float, default=0.12)

    p.add_argument("--hard-instability-threshold", type=float, default=0.45)
    p.add_argument("--hard-margin-threshold", type=float, default=0.09)
    p.add_argument("--hard-outside-threshold", type=float, default=0.04)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    targets_root = Path(args.targets_root)
    seeds = _parse_int_csv(args.seeds)

    per_seed: list[dict[str, Any]] = []
    failure_diagnostics: list[dict[str, Any]] = []
    support_diagnostics: list[dict[str, Any]] = []

    for seed in seeds:
        cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=float(args.near_tie_margin),
            feature_set=str(args.feature_set),
            train_pairwise=True,
            train_pointwise=True,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
        )

        # load canonical rank-instability regime as the unified feature signal source
        rank_raw = load_label_artifacts(targets_root / f"regime_{args.rank_instability_regime}")
        rank_tables = prepare_learning_tables(rank_raw, cfg)
        rank_candidates = rank_tables["candidates"]
        rank_pairs = rank_tables["pairwise"]
        states, oracle_best, feature_table = _build_state_tables(rank_candidates)
        near_tie_flags, adjacent_flags = _state_flags(rank_pairs)
        pair_lookup = _pair_lookup(rank_pairs)

        support_diagnostics.append(
            {
                "seed": int(seed),
                "test_states": len(states),
                "test_pairs": len([r for r in rank_pairs if str(r.get("split")) == "test"]),
                "near_tie_state_rate": float(sum(int(v) for v in near_tie_flags.values()) / max(1, len(states))),
                "adjacent_state_rate": float(sum(int(v) for v in adjacent_flags.values()) / max(1, len(states))),
                "rank_instability_state_label_rate": float(
                    sum(1 for sid in states if any(bool(rr.get("rank_instability_state_label", False)) for rr in states[sid])) / max(1, len(states))
                ),
                "rank_instability_pair_label_rate": float(
                    sum(1 for r in rank_pairs if str(r.get("split")) == "test" and bool(r.get("rank_instability_pair_label", False)))
                    / max(1, len([r for r in rank_pairs if str(r.get("split")) == "test"]))
                ),
            }
        )

        # models / scorers
        base_raw = load_label_artifacts(targets_root / f"regime_{args.baseline_regime}")
        base_models = train_models(prepare_learning_tables(base_raw, cfg), cfg)
        base_pair = base_models.get("pairwise", {})
        if str(base_pair.get("status")) == "ok":
            base_scorer_raw = scorer_from_model(base_pair)
            base_scorer = lambda x: float(base_scorer_raw({"x": x}))
        else:
            base_scorer = lambda _x: 0.0

        ms_raw = load_label_artifacts(targets_root / f"regime_{args.multistep_regime}")
        ms_tables = prepare_learning_tables(ms_raw, cfg)
        ms_model = _fit_linear_pointwise(ms_tables["candidates"], target_field="multistep_branch_utility_target", seed=int(seed))
        ms_scorer = _linear_scorer(ms_model) if str(ms_model.get("status")) == "ok" else (lambda _x: 0.0)

        d_raw = load_label_artifacts(targets_root / f"regime_{args.discounted_regime}")
        d_tables = prepare_learning_tables(d_raw, cfg)
        d_model = _fit_linear_pointwise(d_tables["candidates"], target_field="multistep_branch_utility_target", seed=int(seed))

        c_raw = load_label_artifacts(targets_root / f"regime_{args.curve_regime}")
        c_tables = prepare_learning_tables(c_raw, cfg)
        c_model = _fit_linear_pointwise(c_tables["candidates"], target_field="compute_response_curve_decision_scalar", seed=int(seed))

        rank_models = train_models(rank_tables, cfg)
        rank_pair_model = rank_models.get("pairwise", {})
        if str(rank_pair_model.get("status")) == "ok":
            rank_scorer_raw = scorer_from_model(rank_pair_model)
            rank_scorer = lambda x: float(rank_scorer_raw({"x": x}))
        else:
            rank_scorer = lambda _x: 0.0

        instability_model = _fit_instability_head(rank_pairs, seed=int(seed))

        policies: list[tuple[str, Callable[[list[float]], float], bool]] = [
            ("baseline_all_pairs", base_scorer, False),
            ("multistep_k3_current", ms_scorer, False),
            ("rank_instability_aware_current", rank_scorer, True),
            ("defer_on_instability", ms_scorer, True),
            ("instability_penalized_top_score", ms_scorer, True),
            ("instability_outside_option_gate", ms_scorer, True),
            ("selective_hard_case_abstention", ms_scorer, True),
        ]

        for policy_name, scorer, uses_instability in policies:
            decision_rows: list[dict[str, Any]] = []
            for sid, cands in states.items():
                ranked = sorted(
                    [
                        {
                            "branch_id": str(r.get("branch_id", "")),
                            "raw_score": float(scorer(r["x"])),
                            "outside_gap": float(r.get("branch_vs_outside_gap", 0.0)),
                            "multistep_delta": float(r.get("multistep_branch_utility_delta_vs_onestep", 0.0)),
                            "state_instability_score": float(r.get("rank_instability_state_score", 0.0)),
                            "state_instability_label": bool(r.get("rank_instability_state_label", False)),
                        }
                        for r in cands
                    ],
                    key=lambda rr: rr["raw_score"],
                    reverse=True,
                )
                if not ranked:
                    continue
                top = ranked[0]
                second = ranked[1] if len(ranked) > 1 else ranked[0]
                gap_raw = float(top["raw_score"] - second["raw_score"])
                prow = _top2_pair_row(sid, str(top["branch_id"]), str(second["branch_id"]), pair_lookup)
                inst_prob = 0.0
                if uses_instability and str(instability_model.get("status")) == "ok" and prow is not None:
                    inst_prob = _instability_prob(instability_model, prow)

                choice, defer, reasons, adjusted = _policy_decision(
                    policy=policy_name,
                    sid=sid,
                    ranked=ranked,
                    top2_row=prow,
                    instability_prob=inst_prob,
                    near_tie=bool(near_tie_flags.get(sid, False)),
                    adjacent=bool(adjacent_flags.get(sid, False)),
                    cfg=args,
                )

                oracle_bid = str(oracle_best.get(sid, ""))
                chosen_meta = feature_table.get(sid, {}).get(choice, {})
                oracle_meta = feature_table.get(sid, {}).get(oracle_bid, {})
                delayed_fail = bool(
                    choice
                    and oracle_bid
                    and choice != oracle_bid
                    and float(chosen_meta.get("multistep_delta", 0.0)) > float(oracle_meta.get("multistep_delta", 0.0))
                    and float(chosen_meta.get("outside_gap", 0.0)) < 0.0
                    and float(oracle_meta.get("outside_gap", 0.0)) > 0.0
                )
                decision_rows.append(
                    {
                        "seed": int(seed),
                        "policy": policy_name,
                        "state_id": sid,
                        "choice": choice,
                        "oracle_best": oracle_bid,
                        "defer": bool(defer),
                        "defer_reasons": reasons,
                        "is_near_tie": bool(near_tie_flags.get(sid, False)),
                        "is_adjacent": bool(adjacent_flags.get(sid, False)),
                        "score_gap_top2": gap_raw,
                        "instability_prob_top2": float(inst_prob),
                        "chosen_outside_gap": float(chosen_meta.get("outside_gap", 0.0)),
                        "chosen_multistep_delta": float(chosen_meta.get("multistep_delta", 0.0)),
                        "oracle_outside_gap": float(oracle_meta.get("outside_gap", 0.0)),
                        "oracle_multistep_delta": float(oracle_meta.get("multistep_delta", 0.0)),
                        "delayed_payoff_overvaluation_with_outside_option_miss": delayed_fail,
                        "top_candidates": adjusted[:2],
                    }
                )

            metrics, diagnostics = _evaluate(
                rows=decision_rows,
                oracle_best=oracle_best,
                near_tie_flags=near_tie_flags,
                adjacent_flags=adjacent_flags,
            )
            per_seed.append(
                {
                    "seed": int(seed),
                    "policy": policy_name,
                    "metrics": metrics,
                    "model_status": {
                        "base_pairwise": str(base_pair.get("status", "unknown")),
                        "multistep_pointwise": str(ms_model.get("status", "unknown")),
                        "rank_pairwise": str(rank_pair_model.get("status", "unknown")),
                        "instability_head": str(instability_model.get("status", "unknown")),
                        "discounted_anchor": str(d_model.get("status", "unknown")),
                        "curve_anchor": str(c_model.get("status", "unknown")),
                    },
                }
            )
            failure_diagnostics.append(
                {
                    "seed": int(seed),
                    "policy": policy_name,
                    "metrics": metrics,
                    "diagnostics": diagnostics,
                    "rows": decision_rows,
                }
            )

    policies_sorted = sorted(set(str(r["policy"]) for r in per_seed))
    aggregate = {p: _aggregate_mode([r for r in per_seed if str(r["policy"]) == p]) for p in policies_sorted}

    ms = aggregate.get("multistep_k3_current", {})
    comparison_vs_multistep: dict[str, Any] = {}
    for policy in policies_sorted:
        if policy == "multistep_k3_current":
            continue
        vals = aggregate.get(policy, {})
        comparison_vs_multistep[policy] = {
            "delta_accepted_accuracy": float(vals.get("accepted_accuracy_mean", 0.0) - ms.get("accepted_accuracy_mean", 0.0)),
            "delta_coverage": float(vals.get("coverage_mean", 0.0) - ms.get("coverage_mean", 0.0)),
            "delta_near_tie_accepted_accuracy": float(vals.get("near_tie_accepted_accuracy_mean", 0.0) - ms.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_adjacent_rank_accepted_accuracy": float(vals.get("adjacent_rank_accepted_accuracy_mean", 0.0) - ms.get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "delta_strict_hard_slice_accepted_accuracy": float(vals.get("strict_hard_slice_accepted_accuracy_mean", 0.0) - ms.get("strict_hard_slice_accepted_accuracy_mean", 0.0)),
            "delta_fragile_overconfident_wrong_rate": float(
                vals.get("fragile_overconfident_wrong_rate_on_failures_mean", 0.0)
                - ms.get("fragile_overconfident_wrong_rate_on_failures_mean", 0.0)
            ),
            "delta_delayed_payoff_overvaluation_failures": float(
                vals.get("delayed_payoff_overvaluation_failures_mean", 0.0) - ms.get("delayed_payoff_overvaluation_failures_mean", 0.0)
            ),
            "delta_easy_state_defer_rate": float(vals.get("easy_state_defer_rate_mean", 0.0) - ms.get("easy_state_defer_rate_mean", 0.0)),
            "delta_spillover_non_hard_defer_rate": float(
                vals.get("spillover_non_hard_defer_rate_mean", 0.0) - ms.get("spillover_non_hard_defer_rate_mean", 0.0)
            ),
        }

    best_policy = max(
        policies_sorted,
        key=lambda p: (
            float(aggregate.get(p, {}).get("accepted_accuracy_mean", 0.0)),
            float(aggregate.get(p, {}).get("strict_hard_slice_accepted_accuracy_mean", 0.0)),
        ),
    ) if policies_sorted else ""

    _write_json(
        out_dir / "config_manifest.json",
        {
            "run_id": str(args.run_id),
            "targets_root": str(targets_root),
            "output_dir": str(out_dir),
            "seeds": seeds,
            "feature_set": str(args.feature_set),
            "near_tie_margin": float(args.near_tie_margin),
            "regimes": {
                "baseline": str(args.baseline_regime),
                "multistep": str(args.multistep_regime),
                "discounted": str(args.discounted_regime),
                "curve": str(args.curve_regime),
                "rank_instability": str(args.rank_instability_regime),
            },
            "policy_parameters": {
                "current_instability_threshold": float(args.current_instability_threshold),
                "current_margin_threshold": float(args.current_margin_threshold),
                "defer_instability_threshold": float(args.defer_instability_threshold),
                "defer_margin_threshold": float(args.defer_margin_threshold),
                "penalty_weight": float(args.penalty_weight),
                "penalty_state_score_weight": float(args.penalty_state_score_weight),
                "penalty_outside_weak_floor": float(args.penalty_outside_weak_floor),
                "penalty_defer_instability_threshold": float(args.penalty_defer_instability_threshold),
                "penalty_defer_adjusted_margin_threshold": float(args.penalty_defer_adjusted_margin_threshold),
                "gate_instability_threshold": float(args.gate_instability_threshold),
                "gate_outside_gap_threshold": float(args.gate_outside_gap_threshold),
                "gate_margin_threshold": float(args.gate_margin_threshold),
                "hard_instability_threshold": float(args.hard_instability_threshold),
                "hard_margin_threshold": float(args.hard_margin_threshold),
                "hard_outside_threshold": float(args.hard_outside_threshold),
            },
            "command": " ".join(sys.argv),
        },
    )
    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed})
    _write_json(
        out_dir / "aggregate_comparison_summary.json",
        {
            "aggregate": aggregate,
            "comparison_vs_multistep_k3": comparison_vs_multistep,
            "best_policy_by_accepted_then_strict_hard": best_policy,
        },
    )
    _write_json(out_dir / "failure_diagnostics.json", {"rows": failure_diagnostics})
    _write_json(out_dir / "support_diagnostics.json", {"rows": support_diagnostics})

    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                f"- Command: `{' '.join(sys.argv)}`",
                "- This is a bounded decision-policy pass: no new target family and no new simulator labels were introduced.",
                "- New coupling policies are explicit rule-based action layers that consume existing multistep/outside-gap/instability/margin signals.",
                "- Accepted metrics are computed on non-deferred states only; coverage/defer_rate expose selective behavior.",
                "- Diagnostics include fragile overconfident wrong accepts, delayed-payoff overvaluation failures, and easy-state defer spillover.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(out_dir), "best_policy": best_policy, "policies": policies_sorted}, indent=2))


if __name__ == "__main__":
    main()
