#!/usr/bin/env python3
"""Matched near-tie pointwise-expert fallback experiment with diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    _sigmoid,
    load_label_artifacts,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Near-tie pointwise-expert matched experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--feature-set", choices=["v1", "v2"], default="v2")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--tie-abs-margin-threshold", type=float, default=0.03)
    p.add_argument("--tie-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--tie-std-threshold", type=float, default=0.08)
    p.add_argument("--tie-use-near-tie-flag", action="store_true")
    p.add_argument("--tie-include-approx", action="store_true")
    p.add_argument("--abstain-confidence-threshold", type=float, default=0.20)
    p.add_argument("--calibration-methods", default="none,temperature,platt,isotonic")
    p.add_argument("--primary-calibration", default="temperature")
    p.add_argument("--near-tie-detector-abs-margin", type=float, default=0.03)
    p.add_argument("--near-tie-detector-relative-margin", type=float, default=0.15)
    p.add_argument("--near-tie-detector-std", type=float, default=0.08)
    p.add_argument("--near-tie-detector-confidence-max", type=float, default=0.30)
    p.add_argument("--near-tie-detector-use-near-tie-flag", action="store_true")
    p.add_argument("--near-tie-detector-min-signals", type=int, default=2)
    p.add_argument("--detector-threshold-mode", choices=["base", "strict", "loose"], default="base")
    p.add_argument(
        "--controller-policy",
        choices=["legacy_variants", "strict_coupled_v1", "all"],
        default="all",
        help="Which controller-policy family to evaluate; strict_coupled_v1 is the new stricter routed policy.",
    )
    p.add_argument("--pointwise-margin-min", type=float, default=0.03)
    p.add_argument("--pointwise-fallback-if-uncertain", choices=["pairwise_binary", "generic_pointwise"], default="pairwise_binary")
    p.add_argument("--near-tie-specialized-margin-max", type=float, default=0.08)
    p.add_argument("--near-tie-specialized-min-states", type=int, default=6)
    p.add_argument("--near-tie-reweight-factor", type=float, default=2.5)
    p.add_argument("--adjacent-reweight-factor", type=float, default=1.5)
    p.add_argument("--strict-coupled-rank-gap-max", type=float, default=1.25)
    p.add_argument("--strict-coupled-frontier-std-min", type=float, default=0.09)
    p.add_argument("--strict-coupled-frontier-entropy-min", type=float, default=0.70)
    p.add_argument("--strict-coupled-min-signals", type=int, default=4)
    p.add_argument("--posthoc-deferral-abs-margin-max", type=float, default=0.03)
    p.add_argument("--posthoc-deferral-relative-margin-max", type=float, default=0.15)
    p.add_argument("--posthoc-deferral-std-min", type=float, default=0.08)
    p.add_argument("--posthoc-deferral-confidence-max", type=float, default=0.30)
    p.add_argument("--posthoc-deferral-rank-gap-max", type=float, default=1.25)
    p.add_argument("--posthoc-deferral-frontier-std-min", type=float, default=0.09)
    p.add_argument("--posthoc-deferral-frontier-entropy-min", type=float, default=0.70)
    p.add_argument("--posthoc-deferral-min-signals", type=int, default=4)
    p.add_argument("--posthoc-deferral-require-strict-gate", action="store_true")
    p.add_argument("--deferred-specialized-min-states", type=int, default=6)
    p.add_argument("--reliability-weight-std-scale", type=float, default=6.0)
    p.add_argument("--reliability-weight-min", type=float, default=0.25)
    p.add_argument("--reliability-weight-max", type=float, default=3.0)
    p.add_argument("--improved-specialized-min-states", type=int, default=6)
    p.add_argument("--improved-near-tie-reweight-factor", type=float, default=2.0)
    p.add_argument("--improved-adjacent-reweight-factor", type=float, default=1.75)
    p.add_argument("--improved-uncertainty-weight-scale", type=float, default=1.5)
    p.add_argument("--improved-uncertainty-weight-cap", type=float, default=3.0)
    p.add_argument(
        "--two-stage-threshold-grid",
        default="0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70",
        help="Comma-separated threshold grid for stage-2 defer probability threshold selection.",
    )
    p.add_argument(
        "--two-stage-min-coverage-floor",
        type=float,
        default=0.65,
        help="Minimum validation accepted coverage required by the improved threshold policy.",
    )
    p.add_argument("--pointwise-alpha", type=float, default=1.0)
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _ece(y: list[int], p: list[float], n_bins: int = 10) -> float:
    if not y:
        return 0.0
    arr_y = np.array(y, dtype=float)
    arr_p = np.array(p, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(arr_y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (arr_p >= lo) & (arr_p < hi if i < (n_bins - 1) else arr_p <= hi)
        if not np.any(mask):
            continue
        conf = float(np.mean(arr_p[mask]))
        acc = float(np.mean(arr_y[mask]))
        ece += (np.sum(mask) / n) * abs(conf - acc)
    return float(ece)


def _brier(y: list[int], p: list[float]) -> float:
    if not y:
        return 0.0
    return float(np.mean((np.array(p, dtype=float) - np.array(y, dtype=float)) ** 2))


def _nll(y: list[int], p: list[float]) -> float:
    if not y:
        return 0.0
    arr_y = np.array(y, dtype=float)
    arr_p = np.clip(np.array(p, dtype=float), 1e-6, 1.0 - 1e-6)
    return float(-np.mean(arr_y * np.log(arr_p) + (1.0 - arr_y) * np.log(1.0 - arr_p)))


def _fit_temperature(logits: list[float], y: list[int]) -> dict[str, Any]:
    if not logits:
        return {"status": "insufficient", "temperature": 1.0}
    best_t = 1.0
    best_nll = float("inf")
    for t in [0.25, 0.35, 0.5, 0.7, 1.0, 1.3, 1.6, 2.0, 3.0, 4.0]:
        probs = [_sigmoid(z / t) for z in logits]
        nll = _nll(y, probs)
        if nll < best_nll:
            best_nll = nll
            best_t = t
    return {"status": "ok", "temperature": float(best_t), "val_nll": float(best_nll)}


def _prepare_logits(rows: list[dict[str, Any]], scorer: Callable[[dict[str, Any]], float], split: str) -> tuple[list[float], list[int]]:
    subset = [r for r in rows if str(r.get("split")) == split]
    logits = [float(scorer({"x": r["x_i"]}) - scorer({"x": r["x_j"]})) for r in subset]
    y = [int(r.get("label", 0)) for r in subset]
    return logits, y


def _apply_calibration(method: str, calib_obj: dict[str, Any], logits: list[float]) -> list[float]:
    if method == "none":
        return [_sigmoid(z) for z in logits]
    if method == "temperature":
        t = float(calib_obj.get("temperature", 1.0))
        return [_sigmoid(z / max(t, 1e-6)) for z in logits]
    if method == "platt":
        model = calib_obj.get("model")
        if model is None:
            return [_sigmoid(z) for z in logits]
        probs = model.predict_proba(np.array(logits, dtype=float).reshape(-1, 1))[:, 1]
        return [float(v) for v in probs]
    if method == "isotonic":
        model = calib_obj.get("model")
        if model is None:
            return [_sigmoid(z) for z in logits]
        probs = model.predict(np.array(logits, dtype=float))
        return [float(np.clip(v, 0.0, 1.0)) for v in probs]
    return [_sigmoid(z) for z in logits]


def _fit_calibrators(rows: list[dict[str, Any]], scorer: Callable[[dict[str, Any]], float], methods: list[str]) -> dict[str, Any]:
    val_logits, val_y = _prepare_logits(rows, scorer, "val")
    out: dict[str, Any] = {"split": "val", "n_val": len(val_logits), "methods": {}}
    for m in methods:
        if m == "none":
            probs = [_sigmoid(z) for z in val_logits]
            out["methods"][m] = {"status": "ok", "val_brier": _brier(val_y, probs), "val_ece": _ece(val_y, probs), "val_nll": _nll(val_y, probs)}
        elif m == "temperature":
            fit = _fit_temperature(val_logits, val_y)
            probs = _apply_calibration(m, fit, val_logits)
            fit.update({"val_brier": _brier(val_y, probs), "val_ece": _ece(val_y, probs)})
            out["methods"][m] = fit
        elif m == "platt":
            if len(set(val_y)) < 2 or len(val_y) < 5:
                out["methods"][m] = {"status": "insufficient"}
            else:
                model = LogisticRegression(max_iter=300, random_state=0)
                model.fit(np.array(val_logits, dtype=float).reshape(-1, 1), np.array(val_y, dtype=int))
                probs = _apply_calibration(m, {"model": model}, val_logits)
                out["methods"][m] = {"status": "ok", "model": model, "val_brier": _brier(val_y, probs), "val_ece": _ece(val_y, probs), "val_nll": _nll(val_y, probs)}
        elif m == "isotonic":
            if len(set(val_y)) < 2 or len(val_y) < 8:
                out["methods"][m] = {"status": "insufficient"}
            else:
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(np.array(val_logits, dtype=float), np.array(val_y, dtype=float))
                probs = _apply_calibration(m, {"model": iso}, val_logits)
                out["methods"][m] = {"status": "ok", "model": iso, "val_brier": _brier(val_y, probs), "val_ece": _ece(val_y, probs), "val_nll": _nll(val_y, probs)}
        else:
            out["methods"][m] = {"status": "unknown_method"}
    return out


def _fit_pointwise_ridge(
    candidates: list[dict[str, Any]], *, alpha: float, seed: int, train_filter_fn: Callable[[dict[str, Any]], bool], sample_weight_fn: Callable[[dict[str, Any]], float] | None = None
) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train" and train_filter_fn(r)]
    if len(train) < 6:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    if sample_weight_fn is None:
        w = None
    else:
        w = np.array([max(1e-6, float(sample_weight_fn(r))) for r in train], dtype=float)
    model = Ridge(alpha=float(alpha), random_state=int(seed))
    model.fit(x, y, sample_weight=w)
    return {
        "status": "ok",
        "weights": [float(v) for v in model.coef_],
        "intercept": float(model.intercept_),
        "training_rows": len(train),
        "sample_weight_used": bool(sample_weight_fn is not None),
    }


def _pointwise_scorer(model: dict[str, Any], fallback: Callable[[dict[str, Any]], float]) -> Callable[[dict[str, Any]], float]:
    if str(model.get("status")) != "ok":
        return fallback
    w = [float(v) for v in model.get("weights", [])]
    b = float(model.get("intercept", 0.0))
    return lambda row: float(sum(float(a) * float(bi) for a, bi in zip(w, row["x"])) + b)


def _fit_binary_head(x: list[list[float]], y: list[int], *, seed: int) -> dict[str, Any]:
    if len(x) < 12:
        return {"status": "insufficient_rows", "n_rows": len(x)}
    if len(set(y)) < 2:
        return {
            "status": "single_class",
            "n_rows": len(x),
            "constant_probability": float(y[0]) if y else 0.0,
        }
    model = LogisticRegression(max_iter=400, random_state=seed, class_weight="balanced")
    model.fit(np.array(x, dtype=float), np.array(y, dtype=int))
    return {
        "status": "ok",
        "model": model,
        "n_rows": len(x),
        "positive_rate": float(sum(y) / max(1, len(y))),
    }


def _binary_head_predict_proba(head: dict[str, Any], x: list[list[float]]) -> list[float]:
    if not x:
        return []
    status = str(head.get("status", ""))
    if status == "ok":
        model = head["model"]
        probs = model.predict_proba(np.array(x, dtype=float))[:, 1]
        return [float(p) for p in probs]
    if status == "single_class":
        p = float(head.get("constant_probability", 0.0))
        return [p for _ in x]
    return [0.0 for _ in x]


def _select_two_stage_threshold_defer_rate_constrained(
    *,
    val_rows: list[dict[str, Any]],
    stage1_val_probs: list[float],
    stage2_val_probs: list[float],
    pairwise_fn: Callable[[dict[str, Any]], int],
    specialist_fn: Callable[[dict[str, Any]], int],
    threshold_grid: list[float],
    baseline_val_defer_rate: float,
) -> tuple[float, dict[str, Any]]:
    if not val_rows:
        return 0.5, {"status": "no_val_rows", "policy": "defer_rate_constrained_utility"}
    defer_threshold = 0.5
    best_score = -1e9
    allowed_max_rate = min(0.95, float(baseline_val_defer_rate) + 0.08)
    selected_meta = {
        "status": "ok",
        "policy": "defer_rate_constrained_utility",
        "selected_threshold": float(defer_threshold),
        "selected_forced_accuracy": 0.0,
        "selected_defer_rate": 0.0,
        "allowed_max_defer_rate": float(allowed_max_rate),
        "objective": -1e9,
    }
    for thr in threshold_grid:
        chosen = []
        deferred = 0
        for r, p1, p2 in zip(val_rows, stage1_val_probs, stage2_val_probs):
            should_defer = (float(p1) >= 0.5) and (float(p2) >= float(thr))
            y = int(r.get("label", 0))
            pred = specialist_fn(r) if should_defer else pairwise_fn(r)
            chosen.append(int(pred == y))
            deferred += int(should_defer)
        if not chosen:
            continue
        defer_rate = deferred / len(chosen)
        if defer_rate > allowed_max_rate:
            continue
        forced_acc = sum(chosen) / len(chosen)
        score = forced_acc - 0.05 * defer_rate
        if score > best_score:
            best_score = score
            defer_threshold = float(thr)
            selected_meta = {
                "status": "ok",
                "policy": "defer_rate_constrained_utility",
                "selected_threshold": float(thr),
                "selected_forced_accuracy": float(forced_acc),
                "selected_defer_rate": float(defer_rate),
                "allowed_max_defer_rate": float(allowed_max_rate),
                "objective": float(score),
            }
    return defer_threshold, selected_meta


def _select_two_stage_threshold_accepted_accuracy_coverage_floor(
    *,
    val_rows: list[dict[str, Any]],
    stage1_val_probs: list[float],
    stage2_val_probs: list[float],
    pairwise_fn: Callable[[dict[str, Any]], int],
    specialist_fn: Callable[[dict[str, Any]], int],
    threshold_grid: list[float],
    min_coverage_floor: float,
) -> tuple[float, dict[str, Any]]:
    if not val_rows:
        return 0.5, {"status": "no_val_rows", "policy": "accepted_accuracy_with_coverage_floor"}
    best_threshold = 0.5
    best_tuple = (-1.0, -1.0, -1.0, -1.0)  # accepted_acc, coverage, forced_acc, threshold
    floor = min(1.0, max(0.05, float(min_coverage_floor)))
    any_floor_satisfying = False
    for thr in threshold_grid:
        accepted_correct = 0
        accepted_count = 0
        forced_correct = 0
        deferred = 0
        for r, p1, p2 in zip(val_rows, stage1_val_probs, stage2_val_probs):
            should_defer = (float(p1) >= 0.5) and (float(p2) >= float(thr))
            y = int(r.get("label", 0))
            pair_pred = pairwise_fn(r)
            forced_pred = specialist_fn(r) if should_defer else pair_pred
            forced_correct += int(forced_pred == y)
            if should_defer:
                deferred += 1
                continue
            accepted_count += 1
            accepted_correct += int(pair_pred == y)
        n = len(val_rows)
        coverage = accepted_count / max(1, n)
        accepted_acc = accepted_correct / max(1, accepted_count)
        forced_acc = forced_correct / max(1, n)
        candidate_tuple = (float(accepted_acc), float(coverage), float(forced_acc), -float(thr))
        if coverage >= floor:
            any_floor_satisfying = True
            if candidate_tuple > best_tuple:
                best_tuple = candidate_tuple
                best_threshold = float(thr)
    if not any_floor_satisfying:
        for thr in threshold_grid:
            accepted_correct = 0
            accepted_count = 0
            forced_correct = 0
            for r, p1, p2 in zip(val_rows, stage1_val_probs, stage2_val_probs):
                should_defer = (float(p1) >= 0.5) and (float(p2) >= float(thr))
                y = int(r.get("label", 0))
                pair_pred = pairwise_fn(r)
                forced_pred = specialist_fn(r) if should_defer else pair_pred
                forced_correct += int(forced_pred == y)
                if not should_defer:
                    accepted_count += 1
                    accepted_correct += int(pair_pred == y)
            n = len(val_rows)
            coverage = accepted_count / max(1, n)
            accepted_acc = accepted_correct / max(1, accepted_count)
            forced_acc = forced_correct / max(1, n)
            candidate_tuple = (float(coverage), float(accepted_acc), float(forced_acc), -float(thr))
            if candidate_tuple > best_tuple:
                best_tuple = candidate_tuple
                best_threshold = float(thr)
    selected_accept_acc = max(0.0, best_tuple[0] if any_floor_satisfying else best_tuple[1])
    selected_coverage = max(0.0, best_tuple[1] if any_floor_satisfying else best_tuple[0])
    return best_threshold, {
        "status": "ok",
        "policy": "accepted_accuracy_with_coverage_floor",
        "selected_threshold": float(best_threshold),
        "selected_accepted_accuracy": float(selected_accept_acc),
        "selected_coverage": float(selected_coverage),
        "selected_forced_accuracy": float(best_tuple[2]),
        "min_coverage_floor": float(floor),
        "coverage_floor_satisfied": bool(any_floor_satisfying),
    }


def _slice_acc(rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int], key_fn: Callable[[dict[str, Any]], str]) -> dict[str, float]:
    subset = [r for r in rows if str(r.get("split")) == "test"]
    keys = sorted(set(key_fn(r) for r in subset))
    out: dict[str, float] = {}
    for k in keys:
        rs = [r for r in subset if key_fn(r) == k]
        if rs:
            out[k] = sum(int(pred_fn(r) == int(r.get("label", 0))) for r in rs) / len(rs)
    return out


def _evaluate_formulation(
    pair_rows: list[dict[str, Any]], *, decision_fn: Callable[[dict[str, Any]], int | None], forced_fn: Callable[[dict[str, Any]], int]
) -> dict[str, float]:
    test_rows = [r for r in pair_rows if str(r.get("split")) == "test"]
    accepted = [r for r in test_rows if decision_fn(r) is not None]

    def _acc(rows: list[dict[str, Any]], fn: Callable[[dict[str, Any]], int | None]) -> float:
        if not rows:
            return 0.0
        return sum(int((fn(r) if fn(r) is not None else 0) == int(r.get("label", 0))) for r in rows) / len(rows)

    near = [r for r in test_rows if bool(r.get("near_tie_flag", False))]
    adjacent = [r for r in test_rows if str(r.get("pair_type", "")) == "adjacent_rank"]
    return {
        "accepted_pair_accuracy": _acc(accepted, decision_fn),
        "coverage": len(accepted) / max(1, len(test_rows)),
        "abstention_rate": 1.0 - (len(accepted) / max(1, len(test_rows))),
        "forced_pairwise_accuracy": _acc(test_rows, lambda r: forced_fn(r)),
        "near_tie_forced_accuracy": _acc(near, lambda r: forced_fn(r)),
        "adjacent_forced_accuracy": _acc(adjacent, lambda r: forced_fn(r)),
        "test_pairs": float(len(test_rows)),
    }


def _top1_from_decisions(
    pair_rows: list[dict[str, Any]],
    state_to_candidates: dict[str, list[dict[str, Any]]],
    decision_fn: Callable[[dict[str, Any]], int | None],
    fallback_fn: Callable[[dict[str, Any]], int],
) -> float:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in pair_rows:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r["state_id"]), []).append(r)
    ok = 0
    total = 0
    for sid, cands in state_to_candidates.items():
        test_cands = [c for c in cands if str(c.get("split")) == "test"]
        if len(test_cands) < 2:
            continue
        bids = [str(c["branch_id"]) for c in test_cands]
        wins = {b: 0 for b in bids}
        for r in by_state.get(sid, []):
            bi = str(r["branch_i"])
            bj = str(r["branch_j"])
            if bi not in wins or bj not in wins:
                continue
            pred = decision_fn(r)
            if pred is None:
                pred = fallback_fn(r)
            wins[bi if int(pred) == 1 else bj] += 1
        pred_top = max(wins.items(), key=lambda kv: (kv[1], kv[0]))[0]
        true_top = max(test_cands, key=lambda x: float(x.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        ok += int(str(pred_top) == str(true_top))
        total += 1
    return ok / max(1, total)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    regimes = [x.strip() for x in str(args.regimes).split(",") if x.strip()]
    calib_methods = [x.strip() for x in str(args.calibration_methods).split(",") if x.strip()]
    two_stage_threshold_grid = [float(x.strip()) for x in str(args.two_stage_threshold_grid).split(",") if x.strip()]

    detector_cfg = {
        "base": {
            "abs_margin_max": float(args.near_tie_detector_abs_margin),
            "relative_margin_max": float(args.near_tie_detector_relative_margin),
            "uncertainty_std_min": float(args.near_tie_detector_std),
            "calibrated_confidence_max": float(args.near_tie_detector_confidence_max),
            "min_triggered_signals": int(args.near_tie_detector_min_signals),
        },
    }
    detector_cfg["strict"] = {
        "abs_margin_max": detector_cfg["base"]["abs_margin_max"] * 0.8,
        "relative_margin_max": detector_cfg["base"]["relative_margin_max"] * 0.8,
        "uncertainty_std_min": detector_cfg["base"]["uncertainty_std_min"] * 1.2,
        "calibrated_confidence_max": detector_cfg["base"]["calibrated_confidence_max"] * 0.8,
        "min_triggered_signals": max(2, int(detector_cfg["base"]["min_triggered_signals"])),
    }
    detector_cfg["loose"] = {
        "abs_margin_max": detector_cfg["base"]["abs_margin_max"] * 1.25,
        "relative_margin_max": detector_cfg["base"]["relative_margin_max"] * 1.25,
        "uncertainty_std_min": detector_cfg["base"]["uncertainty_std_min"] * 0.8,
        "calibrated_confidence_max": min(0.98, detector_cfg["base"]["calibrated_confidence_max"] * 1.25),
        "min_triggered_signals": max(1, int(detector_cfg["base"]["min_triggered_signals"]) - 1),
    }
    active_detector = detector_cfg[str(args.detector_threshold_mode)]

    detailed: dict[str, Any] = {
        "run_id": args.run_id,
        "seeds": seeds,
        "regimes": regimes,
        "feature_set": args.feature_set,
        "calibration_methods": calib_methods,
        "detector_threshold_mode": args.detector_threshold_mode,
        "detector_configs": detector_cfg,
        "active_detector_config": active_detector,
        "pointwise_expert_config": {
            "pointwise_margin_min": float(args.pointwise_margin_min),
            "pointwise_fallback_if_uncertain": str(args.pointwise_fallback_if_uncertain),
            "near_tie_specialized_margin_max": float(args.near_tie_specialized_margin_max),
            "near_tie_specialized_min_states": int(args.near_tie_specialized_min_states),
            "near_tie_reweight_factor": float(args.near_tie_reweight_factor),
            "adjacent_reweight_factor": float(args.adjacent_reweight_factor),
        },
        "strict_coupled_gate_config": {
            "rank_gap_abs_max": float(args.strict_coupled_rank_gap_max),
            "frontier_score_std_min": float(args.strict_coupled_frontier_std_min),
            "frontier_entropy_min": float(args.strict_coupled_frontier_entropy_min),
            "min_triggered_signals": int(args.strict_coupled_min_signals),
        },
        "improved_specialized_expert_config": {
            "min_states": int(args.improved_specialized_min_states),
            "near_tie_reweight_factor": float(args.improved_near_tie_reweight_factor),
            "adjacent_reweight_factor": float(args.improved_adjacent_reweight_factor),
            "uncertainty_weight_scale": float(args.improved_uncertainty_weight_scale),
            "uncertainty_weight_cap": float(args.improved_uncertainty_weight_cap),
        },
        "two_stage_threshold_policy_config": {
            "threshold_grid": two_stage_threshold_grid,
            "min_coverage_floor": float(args.two_stage_min_coverage_floor),
        },
        "posthoc_deferral_config": {
            "abs_margin_max": float(args.posthoc_deferral_abs_margin_max),
            "relative_margin_max": float(args.posthoc_deferral_relative_margin_max),
            "uncertainty_std_min": float(args.posthoc_deferral_std_min),
            "calibrated_confidence_max": float(args.posthoc_deferral_confidence_max),
            "rank_gap_abs_max": float(args.posthoc_deferral_rank_gap_max),
            "frontier_score_std_min": float(args.posthoc_deferral_frontier_std_min),
            "frontier_entropy_min": float(args.posthoc_deferral_frontier_entropy_min),
            "min_triggered_signals": int(args.posthoc_deferral_min_signals),
            "require_strict_coupled_gate": bool(args.posthoc_deferral_require_strict_gate),
            "deferred_specialized_min_states": int(args.deferred_specialized_min_states),
        },
        "reliability_weight_config": {
            "std_scale": float(args.reliability_weight_std_scale),
            "weight_min": float(args.reliability_weight_min),
            "weight_max": float(args.reliability_weight_max),
        },
        "results": {},
    }
    summary_rows: list[dict[str, Any]] = []

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            continue
        detailed["results"][regime] = {}

        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                feature_set=str(args.feature_set),
                near_tie_margin=float(args.near_tie_margin),
                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                tie_std_threshold=float(args.tie_std_threshold),
                tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                tie_include_approx=bool(args.tie_include_approx),
                train_pairwise_ternary=False,
                pointwise_alpha=float(args.pointwise_alpha),
            )
            tables = prepare_learning_tables(load_label_artifacts(regime_dir), cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts" / f"{regime}_s{seed}")

            pair_model = models.get("pairwise", {})
            point_model = models.get("pointwise", {})
            if str(pair_model.get("status")) != "ok" or str(point_model.get("status")) != "ok":
                continue
            pair_score = scorer_from_model(pair_model)
            point_generic_score = scorer_from_model(point_model)
            candidate_lookup = {
                (str(c["state_id"]), str(c["branch_id"])): c
                for c in tables["candidates"]
            }

            calibrators = _fit_calibrators(tables["pairwise"], pair_score, calib_methods)
            test_logits, test_y = _prepare_logits(tables["pairwise"], pair_score, "test")
            calibration_eval = {
                method: {
                    "test_brier": _brier(test_y, _apply_calibration(method, mobj, test_logits)),
                    "test_ece": _ece(test_y, _apply_calibration(method, mobj, test_logits)),
                    "test_nll": _nll(test_y, _apply_calibration(method, mobj, test_logits)),
                }
                for method, mobj in calibrators["methods"].items()
            }

            def _calib_prob(row: dict[str, Any], method: str) -> float:
                z = float(pair_score({"x": row["x_i"]}) - pair_score({"x": row["x_j"]}))
                return _apply_calibration(method, calibrators["methods"].get(method, {}), [z])[0]

            def _pairwise_binary(row: dict[str, Any]) -> int:
                return 1 if (pair_score({"x": row["x_i"]}) - pair_score({"x": row["x_j"]})) >= 0.0 else 0

            def _is_near_tie(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
                margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
                rel_margin = float(row.get("relative_margin", 1e9))
                pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
                confidence = abs(_calib_prob(row, str(args.primary_calibration)) - 0.5) * 2.0
                near_tie_flag = bool(row.get("near_tie_flag", False))
                signals = {
                    "abs_margin": margin_abs <= float(active_detector["abs_margin_max"]),
                    "relative_margin": rel_margin <= float(active_detector["relative_margin_max"]),
                    "uncertainty_std": pair_std >= float(active_detector["uncertainty_std_min"]),
                    "calibrated_confidence": confidence <= float(active_detector["calibrated_confidence_max"]),
                    "supervised_near_tie_flag": bool(args.near_tie_detector_use_near_tie_flag) and near_tie_flag,
                }
                trig = sum(int(v) for v in signals.values())
                return trig >= int(active_detector["min_triggered_signals"]), {
                    "margin_abs": margin_abs,
                    "relative_margin": rel_margin,
                    "pair_std": pair_std,
                    "confidence": confidence,
                    "signals": signals,
                    "triggered_signals": trig,
                }

            def _strict_coupled_gate(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
                is_base, base_meta = _is_near_tie(row)
                if not is_base:
                    return False, {
                        **base_meta,
                        "strict_gate_signals": {},
                        "strict_gate_triggered_signals": 0,
                        "strict_gate_reason": "base_detector_off",
                    }
                ci = candidate_lookup.get((str(row["state_id"]), str(row["branch_i"])), {})
                cj = candidate_lookup.get((str(row["state_id"]), str(row["branch_j"])), {})
                fi = ci.get("features_branch_v2", {}) if isinstance(ci.get("features_branch_v2"), dict) else {}
                fj = cj.get("features_branch_v2", {}) if isinstance(cj.get("features_branch_v2"), dict) else {}
                rank_gap_abs = abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0)))
                frontier_std_mean = 0.5 * (float(fi.get("frontier_score_std", 0.0)) + float(fj.get("frontier_score_std", 0.0)))
                frontier_entropy_mean = 0.5 * (float(fi.get("frontier_score_entropy", 0.0)) + float(fj.get("frontier_score_entropy", 0.0)))
                # Stricter routed ambiguity gate:
                # 1) require base near-tie detector,
                # 2) require pair-level ambiguity signature + frontier-dispersion context.
                strict_signals = {
                    "abs_margin_tight": float(base_meta["margin_abs"]) <= float(active_detector["abs_margin_max"]) * 0.9,
                    "relative_margin_tight": float(base_meta["relative_margin"]) <= float(active_detector["relative_margin_max"]) * 0.9,
                    "high_uncertainty": float(base_meta["pair_std"]) >= float(active_detector["uncertainty_std_min"]) * 1.1,
                    "low_confidence": float(base_meta["confidence"]) <= float(active_detector["calibrated_confidence_max"]) * 0.9,
                    "rank_gap_small": rank_gap_abs <= float(args.strict_coupled_rank_gap_max),
                    "frontier_dispersion": (
                        frontier_std_mean >= float(args.strict_coupled_frontier_std_min)
                        or frontier_entropy_mean >= float(args.strict_coupled_frontier_entropy_min)
                    ),
                }
                if bool(args.near_tie_detector_use_near_tie_flag):
                    strict_signals["supervised_near_tie_flag"] = bool(row.get("near_tie_flag", False))
                strict_trig = sum(int(v) for v in strict_signals.values())
                strict_ok = strict_trig >= int(args.strict_coupled_min_signals)
                return bool(strict_ok), {
                    **base_meta,
                    "rank_gap_abs": rank_gap_abs,
                    "frontier_score_std_mean": frontier_std_mean,
                    "frontier_entropy_mean": frontier_entropy_mean,
                    "strict_gate_signals": strict_signals,
                    "strict_gate_triggered_signals": strict_trig,
                    "strict_gate_reason": "ok" if strict_ok else "insufficient_signals",
                }

            def _posthoc_deferral_gate(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
                strict_on, strict_meta = _strict_coupled_gate(row)
                margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
                rel_margin = float(row.get("relative_margin", 1e9))
                pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
                confidence = abs(_calib_prob(row, str(args.primary_calibration)) - 0.5) * 2.0
                near_tie_flag = bool(row.get("near_tie_flag", False))
                signals = {
                    "abs_margin": margin_abs <= float(args.posthoc_deferral_abs_margin_max),
                    "relative_margin": rel_margin <= float(args.posthoc_deferral_relative_margin_max),
                    "uncertainty_std": pair_std >= float(args.posthoc_deferral_std_min),
                    "calibrated_confidence": confidence <= float(args.posthoc_deferral_confidence_max),
                    "near_tie_flag": near_tie_flag,
                    "rank_gap_small": float(strict_meta.get("rank_gap_abs", 1e9)) <= float(args.posthoc_deferral_rank_gap_max),
                    "frontier_dispersion": (
                        float(strict_meta.get("frontier_score_std_mean", 0.0)) >= float(args.posthoc_deferral_frontier_std_min)
                        or float(strict_meta.get("frontier_entropy_mean", 0.0)) >= float(args.posthoc_deferral_frontier_entropy_min)
                    ),
                }
                trig = sum(int(v) for v in signals.values())
                defer = trig >= int(args.posthoc_deferral_min_signals)
                if bool(args.posthoc_deferral_require_strict_gate):
                    defer = bool(defer and strict_on)
                return bool(defer), {
                    "strict_gate_on": bool(strict_on),
                    "margin_abs": margin_abs,
                    "relative_margin": rel_margin,
                    "pair_std": pair_std,
                    "confidence": confidence,
                    "signals": signals,
                    "triggered_signals": trig,
                }

            state_near_tie_train: set[str] = set()
            state_adjacent_train: set[str] = set()
            for pr in tables["pairwise"]:
                if str(pr.get("split")) != "train":
                    continue
                nt, meta = _is_near_tie(pr)
                if nt or float(meta["margin_abs"]) <= float(args.near_tie_specialized_margin_max):
                    state_near_tie_train.add(str(pr["state_id"]))
                if str(pr.get("pair_type", "")) == "adjacent_rank":
                    state_adjacent_train.add(str(pr["state_id"]))

            if len(state_near_tie_train) >= int(args.near_tie_specialized_min_states):
                specialized_model = _fit_pointwise_ridge(
                    tables["candidates"],
                    alpha=float(args.pointwise_alpha),
                    seed=seed,
                    train_filter_fn=lambda r: str(r.get("state_id")) in state_near_tie_train,
                )
            else:
                specialized_model = {
                    "status": "insufficient_near_tie_states",
                    "training_rows": 0,
                    "required_min_states": int(args.near_tie_specialized_min_states),
                }
            state_strict_hard_train: set[str] = set()
            for pr in tables["pairwise"]:
                if str(pr.get("split")) != "train":
                    continue
                strict_on, _ = _strict_coupled_gate(pr)
                if strict_on:
                    state_strict_hard_train.add(str(pr["state_id"]))
            state_posthoc_deferred_train: set[str] = set()
            for pr in tables["pairwise"]:
                if str(pr.get("split")) != "train":
                    continue
                is_def, _ = _posthoc_deferral_gate(pr)
                if is_def:
                    state_posthoc_deferred_train.add(str(pr["state_id"]))

            state_pair_rows_train: dict[str, list[dict[str, Any]]] = {}
            for pr in tables["pairwise"]:
                if str(pr.get("split")) == "train":
                    state_pair_rows_train.setdefault(str(pr["state_id"]), []).append(pr)

            state_reliability_weight: dict[str, float] = {}
            for sid, prs in state_pair_rows_train.items():
                n = max(1, len(prs))
                near_tie_ratio = sum(int(bool(r.get("near_tie_flag", False))) for r in prs) / n
                adjacent_ratio = sum(int(str(r.get("pair_type", "")) == "adjacent_rank") for r in prs) / n
                deferred_ratio = sum(int(_posthoc_deferral_gate(r)[0]) for r in prs) / n
                exact_like_ratio = sum(
                    int(str(r.get("label_source", "")) in {"exact_original", "exact_promoted"} or str(r.get("pair_mode_provenance", "")) in {"exact", "mixed"})
                    for r in prs
                ) / n
                margin_abs_mean = sum(float(r.get("margin_abs", abs(float(r.get("margin", 0.0))))) for r in prs) / n
                pair_std_mean = sum(float(r.get("pair_uncertainty_std_mean", r.get("pair_allocation_value_std", 0.0))) for r in prs) / n
                margin_reliability = min(1.5, max(0.5, margin_abs_mean / max(1e-6, float(args.posthoc_deferral_abs_margin_max))))
                std_reliability = 1.0 / (1.0 + float(args.reliability_weight_std_scale) * max(0.0, pair_std_mean))
                weight = (
                    (1.0 + 0.8 * near_tie_ratio + 0.5 * adjacent_ratio + 0.7 * deferred_ratio)
                    * (1.0 + 0.4 * exact_like_ratio)
                    * margin_reliability
                    * std_reliability
                )
                state_reliability_weight[sid] = min(float(args.reliability_weight_max), max(float(args.reliability_weight_min), float(weight)))

            improved_state_pool = set(state_near_tie_train)
            if len(improved_state_pool) >= int(args.improved_specialized_min_states):
                improved_specialized_model = _fit_pointwise_ridge(
                    tables["candidates"],
                    alpha=float(args.pointwise_alpha),
                    seed=seed,
                    train_filter_fn=lambda r: str(r.get("state_id")) in improved_state_pool,
                    sample_weight_fn=lambda r: min(
                        float(args.improved_uncertainty_weight_cap),
                        max(
                            0.25,
                            (
                                float(args.improved_near_tie_reweight_factor)
                                if str(r.get("state_id")) in state_strict_hard_train
                                else 1.0
                            )
                            * (
                                float(args.improved_adjacent_reweight_factor)
                                if str(r.get("state_id")) in state_adjacent_train
                                else 1.0
                            )
                            * (
                                1.0
                                / (
                                    1.0
                                    + float(args.improved_uncertainty_weight_scale)
                                    * max(0.0, float(r.get("allocation_value_std", 0.0)))
                                )
                            ),
                        ),
                    ),
                )
            else:
                improved_specialized_model = {
                    "status": "insufficient_strict_hard_states",
                    "training_rows": 0,
                    "required_min_states": int(args.improved_specialized_min_states),
                }
            reweighted_model = _fit_pointwise_ridge(
                tables["candidates"],
                alpha=float(args.pointwise_alpha),
                seed=seed,
                train_filter_fn=lambda _r: True,
                sample_weight_fn=lambda r: (
                    float(args.near_tie_reweight_factor) if str(r.get("state_id")) in state_near_tie_train else 1.0
                ) * (
                    float(args.adjacent_reweight_factor) if str(r.get("state_id")) in state_adjacent_train else 1.0
                ),
            )
            if len(state_posthoc_deferred_train) >= int(args.deferred_specialized_min_states):
                deferred_specialized_model = _fit_pointwise_ridge(
                    tables["candidates"],
                    alpha=float(args.pointwise_alpha),
                    seed=seed,
                    train_filter_fn=lambda r: str(r.get("state_id")) in state_posthoc_deferred_train,
                )
            else:
                deferred_specialized_model = {
                    "status": "insufficient_posthoc_deferred_states",
                    "training_rows": 0,
                    "required_min_states": int(args.deferred_specialized_min_states),
                }
            reliability_weighted_model = _fit_pointwise_ridge(
                tables["candidates"],
                alpha=float(args.pointwise_alpha),
                seed=seed,
                train_filter_fn=lambda _r: True,
                sample_weight_fn=lambda r: float(state_reliability_weight.get(str(r.get("state_id")), 1.0)),
            )

            point_specialized_score = _pointwise_scorer(specialized_model, point_generic_score)
            point_improved_specialized_score = _pointwise_scorer(improved_specialized_model, point_specialized_score)
            point_deferred_specialized_score = _pointwise_scorer(deferred_specialized_model, point_specialized_score)
            point_reliability_weighted_score = _pointwise_scorer(reliability_weighted_model, point_specialized_score)
            point_reweighted_score = _pointwise_scorer(reweighted_model, point_generic_score)

            def _point_decision(row: dict[str, Any], scorer: Callable[[dict[str, Any]], float]) -> tuple[int, float]:
                g = float(scorer({"x": row["x_i"]}) - scorer({"x": row["x_j"]}))
                return (1 if g >= 0.0 else 0), abs(g)

            def _near_tie_pointwise_route(
                row: dict[str, Any],
                scorer: Callable[[dict[str, Any]], float],
                gate_fn: Callable[[dict[str, Any]], tuple[bool, dict[str, Any]]],
            ) -> int:
                gate_on, _ = gate_fn(row)
                if not gate_on:
                    return _pairwise_binary(row)
                p_pred, pgap = _point_decision(row, scorer)
                if pgap >= float(args.pointwise_margin_min):
                    return p_pred
                if str(args.pointwise_fallback_if_uncertain) == "generic_pointwise":
                    return _point_decision(row, point_generic_score)[0]
                return _pairwise_binary(row)

            def _abstain_pairwise(row: dict[str, Any]) -> int | None:
                p = _calib_prob(row, str(args.primary_calibration))
                conf = abs(p - 0.5) * 2.0
                if conf < float(args.abstain_confidence_threshold):
                    return None
                return 1 if p >= 0.5 else 0

            def _never_defer(_row: dict[str, Any]) -> bool:
                return False

            def _tie_aware_decision(row: dict[str, Any]) -> int | None:
                is_deferred, _ = _posthoc_deferral_gate(row)
                if is_deferred:
                    return None
                return _pairwise_binary(row)

            def _tie_aware_forced(row: dict[str, Any]) -> int:
                is_deferred, _ = _posthoc_deferral_gate(row)
                if not is_deferred:
                    return _pairwise_binary(row)
                p_pred, pgap = _point_decision(row, point_specialized_score)
                if pgap >= float(args.pointwise_margin_min):
                    return p_pred
                return _pairwise_binary(row)

            def _tie_aware_forced_improved(row: dict[str, Any]) -> int:
                is_deferred, _ = _posthoc_deferral_gate(row)
                if not is_deferred:
                    return _pairwise_binary(row)
                p_pred, pgap = _point_decision(row, point_deferred_specialized_score)
                if pgap >= float(args.pointwise_margin_min):
                    return p_pred
                return _pairwise_binary(row)

            def _tie_aware_forced_reliability_weighted(row: dict[str, Any]) -> int:
                is_deferred, _ = _posthoc_deferral_gate(row)
                if not is_deferred:
                    return _pairwise_binary(row)
                p_pred, pgap = _point_decision(row, point_reliability_weighted_score)
                if pgap >= float(args.pointwise_margin_min):
                    return p_pred
                return _pairwise_binary(row)

            def _specialist_forced_for_defer_target(row: dict[str, Any]) -> int:
                p_pred, pgap = _point_decision(row, point_specialized_score)
                if pgap >= float(args.pointwise_margin_min):
                    return p_pred
                return _pairwise_binary(row)

            def _defer_feature_vector(row: dict[str, Any]) -> list[float]:
                ci = candidate_lookup.get((str(row["state_id"]), str(row["branch_i"])), {})
                cj = candidate_lookup.get((str(row["state_id"]), str(row["branch_j"])), {})
                fi = ci.get("features_branch_v2", {}) if isinstance(ci.get("features_branch_v2"), dict) else {}
                fj = cj.get("features_branch_v2", {}) if isinstance(cj.get("features_branch_v2"), dict) else {}
                pair_i = float(pair_score({"x": row["x_i"]}))
                pair_j = float(pair_score({"x": row["x_j"]}))
                pair_margin = pair_i - pair_j
                pair_prob = _sigmoid(pair_margin)
                pair_pred = 1 if pair_margin >= 0.0 else 0
                pair_conf = abs(pair_prob - 0.5) * 2.0
                p_i = float(point_specialized_score({"x": row["x_i"]}))
                p_j = float(point_specialized_score({"x": row["x_j"]}))
                p_gap = p_i - p_j
                p_pred = 1 if p_gap >= 0.0 else 0
                strict_on, strict_meta = _strict_coupled_gate(row)
                posthoc_on, _ = _posthoc_deferral_gate(row)
                margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
                rel_margin = float(row.get("relative_margin", 1e9))
                pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
                rank_gap_abs = abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0)))
                frontier_std_mean = 0.5 * (float(fi.get("frontier_score_std", 0.0)) + float(fj.get("frontier_score_std", 0.0)))
                frontier_entropy_mean = 0.5 * (float(fi.get("frontier_score_entropy", 0.0)) + float(fj.get("frontier_score_entropy", 0.0)))
                return [
                    margin_abs,
                    rel_margin,
                    pair_std,
                    pair_conf,
                    float(pair_prob),
                    abs(pair_margin),
                    rank_gap_abs,
                    frontier_std_mean,
                    frontier_entropy_mean,
                    1.0 if bool(row.get("near_tie_flag", False)) else 0.0,
                    1.0 if str(row.get("pair_type", "")) == "adjacent_rank" else 0.0,
                    1.0 if strict_on else 0.0,
                    1.0 if posthoc_on else 0.0,
                    float(strict_meta.get("strict_gate_triggered_signals", 0.0)),
                    p_i,
                    p_j,
                    abs(p_gap),
                    1.0 if pair_pred != p_pred else 0.0,
                    abs(pair_margin) - abs(p_gap),
                ]

            defer_feature_names = [
                "margin_abs",
                "relative_margin",
                "pair_uncertainty_std",
                "pair_confidence",
                "pair_probability",
                "pair_margin_abs",
                "rank_gap_abs",
                "frontier_score_std_mean",
                "frontier_entropy_mean",
                "near_tie_flag",
                "adjacent_rank_flag",
                "strict_gate_on",
                "posthoc_gate_on",
                "strict_gate_triggered_signals",
                "pointwise_value_i",
                "pointwise_value_j",
                "pointwise_gap_abs",
                "pairwise_pointwise_disagree",
                "pair_margin_minus_point_gap",
            ]

            def _build_defer_targets(row: dict[str, Any]) -> tuple[int, int]:
                y = int(row.get("label", 0))
                pair_pred = _pairwise_binary(row)
                spec_pred = _specialist_forced_for_defer_target(row)
                pair_err = int(pair_pred != y)
                defer_utility = int((spec_pred == y) and (pair_pred != y))
                return pair_err, defer_utility

            train_rows = [r for r in tables["pairwise"] if str(r.get("split")) == "train"]
            val_rows = [r for r in tables["pairwise"] if str(r.get("split")) == "val"]

            x_train = [_defer_feature_vector(r) for r in train_rows]
            y_train_err = [_build_defer_targets(r)[0] for r in train_rows]
            y_train_defer = [_build_defer_targets(r)[1] for r in train_rows]
            x_val = [_defer_feature_vector(r) for r in val_rows]

            stage1_error_head = _fit_binary_head(x_train, y_train_err, seed=seed)
            # stage-2 defer-benefit head is trained post-hoc on same features + stage-1 risk score.
            stage1_train_probs = _binary_head_predict_proba(stage1_error_head, x_train)
            x_train_stage2 = [xi + [float(p1)] for xi, p1 in zip(x_train, stage1_train_probs)]
            stage2_defer_head = _fit_binary_head(x_train_stage2, y_train_defer, seed=seed + 91)
            stage1_val_probs = _binary_head_predict_proba(stage1_error_head, x_val)
            x_val_stage2 = [xi + [float(p1)] for xi, p1 in zip(x_val, stage1_val_probs)]
            stage2_val_probs = _binary_head_predict_proba(stage2_defer_head, x_val_stage2)

            baseline_val_defer_rate = _mean([1.0 if _posthoc_deferral_gate(r)[0] else 0.0 for r in val_rows]) if val_rows else 0.0
            defer_threshold_legacy, legacy_threshold_meta = _select_two_stage_threshold_defer_rate_constrained(
                val_rows=val_rows,
                stage1_val_probs=stage1_val_probs,
                stage2_val_probs=stage2_val_probs,
                pairwise_fn=_pairwise_binary,
                specialist_fn=_specialist_forced_for_defer_target,
                threshold_grid=two_stage_threshold_grid,
                baseline_val_defer_rate=baseline_val_defer_rate,
            )
            defer_threshold_improved, improved_threshold_meta = _select_two_stage_threshold_accepted_accuracy_coverage_floor(
                val_rows=val_rows,
                stage1_val_probs=stage1_val_probs,
                stage2_val_probs=stage2_val_probs,
                pairwise_fn=_pairwise_binary,
                specialist_fn=_specialist_forced_for_defer_target,
                threshold_grid=two_stage_threshold_grid,
                min_coverage_floor=float(args.two_stage_min_coverage_floor),
            )

            def _learned_two_stage_defer_gate(row: dict[str, Any], *, threshold: float, policy_name: str) -> tuple[bool, dict[str, Any]]:
                x = _defer_feature_vector(row)
                p1 = _binary_head_predict_proba(stage1_error_head, [x])[0]
                x2 = x + [float(p1)]
                p2 = _binary_head_predict_proba(stage2_defer_head, [x2])[0]
                defer = bool((float(p1) >= 0.5) and (float(p2) >= float(threshold)))
                return defer, {
                    "p_pairwise_error": float(p1),
                    "p_defer_utility": float(p2),
                    "defer_threshold": float(threshold),
                    "threshold_policy": str(policy_name),
                }

            def _tie_aware_forced_learned_two_stage(row: dict[str, Any], *, threshold: float, policy_name: str) -> int:
                is_deferred, _ = _learned_two_stage_defer_gate(row, threshold=threshold, policy_name=policy_name)
                if not is_deferred:
                    return _pairwise_binary(row)
                return _specialist_forced_for_defer_target(row)

            variant_specs: list[
                tuple[
                    str,
                    Callable[[dict[str, Any]], int | None],
                    Callable[[dict[str, Any]], int],
                    str,
                    Callable[[dict[str, Any]], bool],
                ]
            ] = [
                ("binary_forced_baseline", lambda r: _pairwise_binary(r), lambda r: _pairwise_binary(r), "pairwise_binary", _never_defer),
                (
                    "abstain_calibrated_pairwise_backup",
                    lambda r: _abstain_pairwise(r),
                    lambda r: _pairwise_binary(r) if _abstain_pairwise(r) is None else int(_abstain_pairwise(r) or 0),
                    "pairwise_binary",
                    _never_defer,
                ),
                (
                    "near_tie_generic_pointwise",
                    lambda r: _near_tie_pointwise_route(r, point_generic_score, _is_near_tie),
                    lambda r: _near_tie_pointwise_route(r, point_generic_score, _is_near_tie),
                    "generic_pointwise",
                    _never_defer,
                ),
                (
                    "near_tie_specialized_pointwise",
                    lambda r: _near_tie_pointwise_route(r, point_specialized_score, _is_near_tie),
                    lambda r: _near_tie_pointwise_route(r, point_specialized_score, _is_near_tie),
                    "specialized_pointwise",
                    _never_defer,
                ),
                (
                    "near_tie_reweighted_pointwise",
                    lambda r: _near_tie_pointwise_route(r, point_reweighted_score, _is_near_tie),
                    lambda r: _near_tie_pointwise_route(r, point_reweighted_score, _is_near_tie),
                    "reweighted_pointwise",
                    _never_defer,
                ),
            ]
            strict_variants: list[
                tuple[
                    str,
                    Callable[[dict[str, Any]], int | None],
                    Callable[[dict[str, Any]], int],
                    str,
                    Callable[[dict[str, Any]], bool],
                ]
            ] = [
                (
                    "strict_coupled_near_tie_specialized_pointwise_v1",
                    lambda r: _near_tie_pointwise_route(r, point_specialized_score, _strict_coupled_gate),
                    lambda r: _near_tie_pointwise_route(r, point_specialized_score, _strict_coupled_gate),
                    "strict_coupled_specialized_pointwise",
                    _never_defer,
                )
                ,
                (
                    "strict_coupled_near_tie_specialized_pointwise_improved_v1",
                    lambda r: _near_tie_pointwise_route(r, point_improved_specialized_score, _strict_coupled_gate),
                    lambda r: _near_tie_pointwise_route(r, point_improved_specialized_score, _strict_coupled_gate),
                    "strict_coupled_specialized_pointwise_improved",
                    _never_defer,
                ),
                (
                    "strict_coupled_tie_aware_posthoc_deferral_v1",
                    lambda r: _tie_aware_decision(r),
                    lambda r: _tie_aware_forced(r),
                    "strict_coupled_tie_aware_posthoc_deferral",
                    lambda r: _posthoc_deferral_gate(r)[0],
                ),
                (
                    "strict_coupled_tie_aware_posthoc_deferral_improved_expert_v1",
                    lambda r: _tie_aware_decision(r),
                    lambda r: _tie_aware_forced_improved(r),
                    "strict_coupled_tie_aware_posthoc_deferral_improved_expert",
                    lambda r: _posthoc_deferral_gate(r)[0],
                ),
                (
                    "strict_coupled_tie_aware_posthoc_deferral_reliability_weighted_expert_v1",
                    lambda r: _tie_aware_decision(r),
                    lambda r: _tie_aware_forced_reliability_weighted(r),
                    "strict_coupled_tie_aware_posthoc_deferral_reliability_weighted_expert",
                    lambda r: _posthoc_deferral_gate(r)[0],
                ),
                (
                    "strict_coupled_tie_aware_learned_two_stage_deferral_v1",
                    lambda r: (
                        None
                        if _learned_two_stage_defer_gate(
                            r, threshold=float(defer_threshold_legacy), policy_name="defer_rate_constrained_utility"
                        )[0]
                        else _pairwise_binary(r)
                    ),
                    lambda r: _tie_aware_forced_learned_two_stage(
                        r, threshold=float(defer_threshold_legacy), policy_name="defer_rate_constrained_utility"
                    ),
                    "strict_coupled_tie_aware_learned_two_stage_deferral",
                    lambda r: _learned_two_stage_defer_gate(
                        r, threshold=float(defer_threshold_legacy), policy_name="defer_rate_constrained_utility"
                    )[0],
                ),
                (
                    "strict_coupled_tie_aware_learned_two_stage_deferral_calibrated_threshold_v1",
                    lambda r: (
                        None
                        if _learned_two_stage_defer_gate(
                            r, threshold=float(defer_threshold_improved), policy_name="accepted_accuracy_with_coverage_floor"
                        )[0]
                        else _pairwise_binary(r)
                    ),
                    lambda r: _tie_aware_forced_learned_two_stage(
                        r, threshold=float(defer_threshold_improved), policy_name="accepted_accuracy_with_coverage_floor"
                    ),
                    "strict_coupled_tie_aware_learned_two_stage_deferral",
                    lambda r: _learned_two_stage_defer_gate(
                        r, threshold=float(defer_threshold_improved), policy_name="accepted_accuracy_with_coverage_floor"
                    )[0],
                )
            ]
            if str(args.controller_policy) == "legacy_variants":
                variants = variant_specs
            elif str(args.controller_policy) == "strict_coupled_v1":
                variants = strict_variants
            else:
                variants = variant_specs + strict_variants

            test_rows = [r for r in tables["pairwise"] if str(r.get("split")) == "test"]

            diag_rows = []
            for r in test_rows:
                is_nt, meta = _is_near_tie(r)
                if not is_nt:
                    continue
                pair_pred = _pairwise_binary(r)
                point_pred, point_gap = _point_decision(r, point_generic_score)
                label = int(r.get("label", 0))
                ci = next(c for c in tables["candidates"] if str(c["state_id"]) == str(r["state_id"]) and str(c["branch_id"]) == str(r["branch_i"]))
                cj = next(c for c in tables["candidates"] if str(c["state_id"]) == str(r["state_id"]) and str(c["branch_id"]) == str(r["branch_j"]))
                fi = ci.get("features_branch_v2", {}) if isinstance(ci.get("features_branch_v2"), dict) else {}
                fj = cj.get("features_branch_v2", {}) if isinstance(cj.get("features_branch_v2"), dict) else {}
                key = f"pairwise_{'ok' if pair_pred==label else 'fail'}__pointwise_{'ok' if point_pred==label else 'fail'}"
                diag_rows.append(
                    {
                        "bucket": key,
                        "margin_abs": float(meta["margin_abs"]),
                        "relative_margin": float(meta["relative_margin"]),
                        "pair_std": float(meta["pair_std"]),
                        "rank_gap_abs": abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0))),
                        "pointwise_value_gap_abs": float(point_gap),
                        "frontier_score_std_mean": 0.5 * (float(fi.get("frontier_score_std", 0.0)) + float(fj.get("frontier_score_std", 0.0))),
                        "frontier_entropy_mean": 0.5 * (float(fi.get("frontier_score_entropy", 0.0)) + float(fj.get("frontier_score_entropy", 0.0))),
                    }
                )

            diag_summary: dict[str, Any] = {}
            for b in sorted(set(r["bucket"] for r in diag_rows)):
                rows_b = [r for r in diag_rows if r["bucket"] == b]
                diag_summary[b] = {
                    "count": len(rows_b),
                    "margin_abs_mean": _mean([x["margin_abs"] for x in rows_b]),
                    "relative_margin_mean": _mean([x["relative_margin"] for x in rows_b]),
                    "pair_std_mean": _mean([x["pair_std"] for x in rows_b]),
                    "rank_gap_abs_mean": _mean([x["rank_gap_abs"] for x in rows_b]),
                    "pointwise_value_gap_abs_mean": _mean([x["pointwise_value_gap_abs"] for x in rows_b]),
                    "frontier_score_std_mean": _mean([x["frontier_score_std_mean"] for x in rows_b]),
                    "frontier_entropy_mean": _mean([x["frontier_entropy_mean"] for x in rows_b]),
                }

            seed_payload: dict[str, Any] = {
                "calibration_fit": {
                    "split": calibrators.get("split"),
                    "n_val": calibrators.get("n_val"),
                    "methods": {k: {kk: vv for kk, vv in v.items() if kk != "model"} for k, v in calibrators.get("methods", {}).items()},
                },
                "calibration_test": calibration_eval,
                "detector_stats": {
                    "test_pairs": len(test_rows),
                    "detected_near_ties": int(sum(int(_is_near_tie(r)[0]) for r in test_rows)),
                    "detected_rate": float(sum(int(_is_near_tie(r)[0]) for r in test_rows) / max(1, len(test_rows))),
                    "detected_near_tie_flag_pairs": int(sum(int(_is_near_tie(r)[0] and bool(r.get("near_tie_flag", False))) for r in test_rows)),
                    "detected_non_near_tie_flag_pairs": int(sum(int(_is_near_tie(r)[0] and not bool(r.get("near_tie_flag", False))) for r in test_rows)),
                    "detected_adjacent_pairs": int(sum(int(_is_near_tie(r)[0] and str(r.get("pair_type", "")) == "adjacent_rank") for r in test_rows)),
                },
                "strict_coupled_gate_stats": {
                    "test_pairs": len(test_rows),
                    "routed_pairs": int(sum(int(_strict_coupled_gate(r)[0]) for r in test_rows)),
                    "routed_rate": float(sum(int(_strict_coupled_gate(r)[0]) for r in test_rows) / max(1, len(test_rows))),
                    "routed_near_tie_flag_pairs": int(sum(int(_strict_coupled_gate(r)[0] and bool(r.get("near_tie_flag", False))) for r in test_rows)),
                    "routed_non_near_tie_flag_pairs": int(sum(int(_strict_coupled_gate(r)[0] and not bool(r.get("near_tie_flag", False))) for r in test_rows)),
                    "routed_adjacent_pairs": int(sum(int(_strict_coupled_gate(r)[0] and str(r.get("pair_type", "")) == "adjacent_rank") for r in test_rows)),
                },
                "pointwise_models": {
                    "generic": {
                        "status": str(point_model.get("status", "unknown")),
                        "training_rows": point_model.get("training_rows", None),
                    },
                    "specialized": {
                        **specialized_model,
                        "near_tie_train_states": len(state_near_tie_train),
                    },
                    "reweighted": {
                        **reweighted_model,
                        "near_tie_train_states": len(state_near_tie_train),
                        "adjacent_train_states": len(state_adjacent_train),
                    },
                    "strict_hard_improved_specialized": {
                        **improved_specialized_model,
                        "strict_hard_train_states": len(state_strict_hard_train),
                        "adjacent_train_states": len(state_adjacent_train),
                        "improved_state_pool": len(improved_state_pool),
                    },
                    "posthoc_deferred_specialized": {
                        **deferred_specialized_model,
                        "posthoc_deferred_train_states": len(state_posthoc_deferred_train),
                    },
                    "reliability_weighted_specialized": {
                        **reliability_weighted_model,
                        "states_with_reliability_weight": len(state_reliability_weight),
                    },
                },
                "learned_two_stage_defer_head": {
                    "feature_names_stage1": defer_feature_names,
                    "feature_names_stage2": defer_feature_names + ["stage1_pairwise_error_probability"],
                    "stage1_pairwise_error_head": {
                        **{k: v for k, v in stage1_error_head.items() if k != "model"},
                    },
                    "stage2_defer_utility_head": {
                        **{k: v for k, v in stage2_defer_head.items() if k != "model"},
                    },
                    "target_definition": "defer=1 iff specialized fallback is correct and pairwise winner is incorrect on the same pair row",
                    "legacy_threshold_selection": legacy_threshold_meta,
                    "improved_threshold_selection": improved_threshold_meta,
                    "baseline_posthoc_val_defer_rate": float(baseline_val_defer_rate),
                    "threshold_grid": two_stage_threshold_grid,
                },
                "near_tie_pairwise_vs_pointwise_diagnostic": {
                    "rows": len(diag_rows),
                    "summary": diag_summary,
                },
                "variants": {},
            }

            for vname, pred_fn, forced_fn, fallback_name, defer_fn in variants:
                met = _evaluate_formulation(tables["pairwise"], decision_fn=pred_fn, forced_fn=forced_fn)
                top1 = _top1_from_decisions(tables["pairwise"], tables["state_to_candidates"], pred_fn, forced_fn)
                by_budget = _slice_acc(tables["pairwise"], forced_fn, lambda r: str(int(r.get("remaining_budget", 0))))
                by_dataset = _slice_acc(tables["pairwise"], forced_fn, lambda r: str(r.get("dataset_name", "unknown")))
                strict_routed = [r for r in test_rows if _strict_coupled_gate(r)[0]]
                strict_routed_near = [r for r in strict_routed if bool(r.get("near_tie_flag", False))]
                deferred_rows = [r for r in test_rows if defer_fn(r)]
                deferred_non_near = [r for r in deferred_rows if not bool(r.get("near_tie_flag", False))]
                strict_routed_acc = 0.0
                strict_routed_near_acc = 0.0
                deferred_subset_acc = 0.0
                if strict_routed:
                    strict_routed_acc = sum(int(forced_fn(r) == int(r.get("label", 0))) for r in strict_routed) / len(strict_routed)
                if strict_routed_near:
                    strict_routed_near_acc = sum(int(forced_fn(r) == int(r.get("label", 0))) for r in strict_routed_near) / len(strict_routed_near)
                if deferred_rows:
                    deferred_subset_acc = sum(int(forced_fn(r) == int(r.get("label", 0))) for r in deferred_rows) / len(deferred_rows)
                seed_payload["variants"][vname] = {
                    **met,
                    "top1_test": float(top1),
                    "forced_accuracy_by_budget": by_budget,
                    "forced_accuracy_by_dataset": by_dataset,
                    "strict_routed_forced_accuracy": float(strict_routed_acc),
                    "strict_routed_near_tie_forced_accuracy": float(strict_routed_near_acc),
                    "strict_routed_test_pairs": len(strict_routed),
                    "strict_routed_near_tie_test_pairs": len(strict_routed_near),
                    "deferred_rate": float(len(deferred_rows) / max(1, len(test_rows))),
                    "deferred_test_pairs": len(deferred_rows),
                    "deferred_non_near_tie_count": len(deferred_non_near),
                    "deferred_subset_forced_accuracy": float(deferred_subset_acc),
                    "fallback_policy": fallback_name,
                }
                summary_rows.append({
                    "regime": regime,
                    "seed": seed,
                    "variant": vname,
                    **met,
                    "top1_test": float(top1),
                    "strict_routed_forced_accuracy": float(strict_routed_acc),
                    "strict_routed_near_tie_forced_accuracy": float(strict_routed_near_acc),
                    "strict_routed_test_pairs": len(strict_routed),
                    "strict_routed_near_tie_test_pairs": len(strict_routed_near),
                    "deferred_rate": float(len(deferred_rows) / max(1, len(test_rows))),
                    "deferred_test_pairs": len(deferred_rows),
                    "deferred_non_near_tie_count": len(deferred_non_near),
                    "deferred_subset_forced_accuracy": float(deferred_subset_acc),
                    "fallback_policy": fallback_name,
                })
            detailed["results"][regime][str(seed)] = seed_payload

    (out_dir / "near_tie_pointwise_expert_results.json").write_text(json.dumps(detailed, indent=2), encoding="utf-8")
    (out_dir / "near_tie_pointwise_expert_summary.json").write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")

    md = [
        "# Near-tie pointwise expert matched experiment",
        "",
        f"- targets_root: `{args.targets_root}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        f"- feature_set: `{args.feature_set}`",
        f"- detector_mode: `{args.detector_threshold_mode}`",
        f"- controller_policy: `{args.controller_policy}`",
        f"- active_detector: `{json.dumps(active_detector, sort_keys=True)}`",
        f"- strict_coupled_gate: `{json.dumps(detailed['strict_coupled_gate_config'], sort_keys=True)}`",
        f"- pointwise_margin_min: `{args.pointwise_margin_min}`",
        "",
    ]
    for regime in sorted(set(r["regime"] for r in summary_rows)):
        md.append(f"## Regime `{regime}`")
        rows_regime = [r for r in summary_rows if r["regime"] == regime]
        for vname in sorted(set(r["variant"] for r in rows_regime)):
            rows = [r for r in rows_regime if r["variant"] == vname]
            md.append(
                f"- {vname}: accepted={_mean([x['accepted_pair_accuracy'] for x in rows]):.4f}, "
                f"coverage={_mean([x['coverage'] for x in rows]):.4f}, forced={_mean([x['forced_pairwise_accuracy'] for x in rows]):.4f}, "
                f"near={_mean([x['near_tie_forced_accuracy'] for x in rows]):.4f}, adj={_mean([x['adjacent_forced_accuracy'] for x in rows]):.4f}, "
                f"top1={_mean([x['top1_test'] for x in rows]):.4f}, "
                f"strict_routed={_mean([x['strict_routed_forced_accuracy'] for x in rows]):.4f}, "
                f"strict_routed_near={_mean([x['strict_routed_near_tie_forced_accuracy'] for x in rows]):.4f}, "
                f"deferred_rate={_mean([x['deferred_rate'] for x in rows]):.4f}, "
                f"deferred_non_near={_mean([x['deferred_non_near_tie_count'] for x in rows]):.2f}, "
                f"deferred_subset_acc={_mean([x['deferred_subset_forced_accuracy'] for x in rows]):.4f}"
            )
        md.append("")
    (out_dir / "near_tie_pointwise_expert_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "rows": len(summary_rows)}, indent=2))


if __name__ == "__main__":
    main()
