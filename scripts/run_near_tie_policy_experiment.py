#!/usr/bin/env python3
"""Matched near-tie policy experiment for branch comparison routing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

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
    p = argparse.ArgumentParser(description="Dedicated near-tie policy matched experiment")
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
    p.add_argument("--tie-require-exact-or-mixed", action="store_true")
    p.add_argument("--abstain-confidence-threshold", type=float, default=0.20)
    p.add_argument("--calibration-methods", default="none,temperature,platt,isotonic")
    p.add_argument("--primary-calibration", default="temperature")
    p.add_argument("--near-tie-detector-abs-margin", type=float, default=0.03)
    p.add_argument("--near-tie-detector-relative-margin", type=float, default=0.15)
    p.add_argument("--near-tie-detector-std", type=float, default=0.08)
    p.add_argument("--near-tie-detector-confidence-max", type=float, default=0.30)
    p.add_argument("--near-tie-detector-use-near-tie-flag", action="store_true")
    p.add_argument("--near-tie-detector-min-signals", type=int, default=2)
    p.add_argument("--score-gap-fallback-threshold", type=float, default=0.02)
    p.add_argument("--balanced-shared-key", default="state_pair_budget")
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
    pair_rows: list[dict[str, Any]],
    *,
    decision_fn: Callable[[dict[str, Any]], int | None],
    forced_fn: Callable[[dict[str, Any]], int],
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


def _stable_hash01(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12)


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
            if int(pred) == 1:
                wins[bi] += 1
            else:
                wins[bj] += 1
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

    detector_cfg = {
        "abs_margin_max": float(args.near_tie_detector_abs_margin),
        "relative_margin_max": float(args.near_tie_detector_relative_margin),
        "uncertainty_std_min": float(args.near_tie_detector_std),
        "calibrated_confidence_max": float(args.near_tie_detector_confidence_max),
        "use_supervised_near_tie_flag": bool(args.near_tie_detector_use_near_tie_flag),
        "min_triggered_signals": int(args.near_tie_detector_min_signals),
    }

    summary_rows: list[dict[str, Any]] = []
    detailed: dict[str, Any] = {
        "run_id": args.run_id,
        "seeds": seeds,
        "regimes": regimes,
        "feature_set": args.feature_set,
        "calibration_methods": calib_methods,
        "abstain_confidence_threshold": args.abstain_confidence_threshold,
        "near_tie_detector_config": detector_cfg,
        "results": {},
    }

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
                tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
                train_pairwise_ternary=False,
            )
            data = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(data, cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts" / f"{regime}_s{seed}")

            pair_model = models.get("pairwise", {})
            point_model = models.get("pointwise", {})
            outside_model = models.get("outside_option", {})
            if str(pair_model.get("status")) != "ok" or str(point_model.get("status")) != "ok":
                continue

            pair_score = scorer_from_model(pair_model)
            point_score = scorer_from_model(point_model)
            outside_score = scorer_from_model(outside_model)

            calibrators = _fit_calibrators(tables["pairwise"], pair_score, calib_methods)
            test_logits, test_y = _prepare_logits(tables["pairwise"], pair_score, "test")
            calibration_eval: dict[str, Any] = {}
            for method, mobj in calibrators["methods"].items():
                probs = _apply_calibration(method, mobj, test_logits)
                calibration_eval[method] = {
                    "test_brier": _brier(test_y, probs),
                    "test_ece": _ece(test_y, probs),
                    "test_nll": _nll(test_y, probs),
                }

            state_cand_map = {(str(c["state_id"]), str(c["branch_id"])): c for c in tables["candidates"]}

            def _pairwise_binary_pred(row: dict[str, Any]) -> int:
                z = float(pair_score({"x": row["x_i"]}) - pair_score({"x": row["x_j"]}))
                return 1 if z >= 0.0 else 0

            def _calib_prob(row: dict[str, Any], method: str) -> float:
                z = float(pair_score({"x": row["x_i"]}) - pair_score({"x": row["x_j"]}))
                return _apply_calibration(method, calibrators["methods"].get(method, {}), [z])[0]

            def _balanced_shared_fallback(row: dict[str, Any]) -> int:
                bi, bj = str(row["branch_i"]), str(row["branch_j"])
                lo, hi = (bi, bj) if bi <= bj else (bj, bi)
                if str(args.balanced_shared_key) == "state_pair_budget":
                    key = f"{row['state_id']}|{lo}|{hi}|{int(row.get('remaining_budget', 0))}"
                else:
                    key = f"{row['state_id']}|{lo}|{hi}"
                return 1 if _stable_hash01(key) >= 0.5 else 0

            def _fallback(policy: str, row: dict[str, Any]) -> int:
                if policy == "pairwise_binary_backup":
                    return _pairwise_binary_pred(row)
                if policy == "pointwise_value":
                    si = float(point_score({"x": row["x_i"]}))
                    sj = float(point_score({"x": row["x_j"]}))
                    return 1 if si >= sj else 0
                if policy == "heuristic_score":
                    ci = state_cand_map[(str(row["state_id"]), str(row["branch_i"]))]
                    cj = state_cand_map[(str(row["state_id"]), str(row["branch_j"]))]
                    si = float(ci.get("features_branch_v1", {}).get("score", 0.0))
                    sj = float(cj.get("features_branch_v1", {}).get("score", 0.0))
                    return 1 if si >= sj else 0
                if policy == "score_gap_heuristic":
                    score_gap_abs = float(row.get("score_gap_abs", row.get("pair_relational_v2", {}).get("score_gap_abs", 0.0)))
                    if score_gap_abs <= float(args.score_gap_fallback_threshold):
                        return _balanced_shared_fallback(row)
                    return _fallback("heuristic_score", row)
                if policy == "balanced_round_robin":
                    return _balanced_shared_fallback(row)
                if policy == "outside_option_aware":
                    pi = float(_sigmoid(outside_score({"x": row["x_i"]})))
                    pj = float(_sigmoid(outside_score({"x": row["x_j"]})))
                    if pi >= 0.5 and pj < 0.5:
                        return 1
                    if pj >= 0.5 and pi < 0.5:
                        return 0
                    return _fallback("pointwise_value", row)
                return _pairwise_binary_pred(row)

            def _is_near_tie(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
                margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
                rel_margin = float(row.get("relative_margin", 1e9))
                pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
                confidence = abs(_calib_prob(row, str(args.primary_calibration)) - 0.5) * 2.0
                near_tie_flag = bool(row.get("near_tie_flag", False))
                signals = {
                    "abs_margin": margin_abs <= float(detector_cfg["abs_margin_max"]),
                    "relative_margin": rel_margin <= float(detector_cfg["relative_margin_max"]),
                    "uncertainty_std": pair_std >= float(detector_cfg["uncertainty_std_min"]),
                    "calibrated_confidence": confidence <= float(detector_cfg["calibrated_confidence_max"]),
                    "supervised_near_tie_flag": bool(detector_cfg["use_supervised_near_tie_flag"]) and near_tie_flag,
                }
                triggered = sum(int(v) for v in signals.values())
                return triggered >= int(detector_cfg["min_triggered_signals"]), {
                    "triggered_signals": triggered,
                    "signals": signals,
                    "confidence": float(confidence),
                    "margin_abs": margin_abs,
                    "relative_margin": rel_margin,
                    "pair_std": pair_std,
                }

            def _abstain_pred(row: dict[str, Any], method: str) -> int | None:
                p = _calib_prob(row, method)
                conf = abs(p - 0.5) * 2.0
                if conf < float(args.abstain_confidence_threshold):
                    return None
                return 1 if p >= 0.5 else 0

            def _near_tie_policy_decision(row: dict[str, Any], policy: str) -> int:
                is_nt, _meta = _is_near_tie(row)
                if is_nt:
                    return _fallback(policy, row)
                return _pairwise_binary_pred(row)

            variants: list[tuple[str, Callable[[dict[str, Any]], int | None], Callable[[dict[str, Any]], int], str, str]] = [
                ("binary_forced_baseline", lambda r: _pairwise_binary_pred(r), lambda r: _pairwise_binary_pred(r), "none", "pairwise_binary_backup"),
                (
                    "abstain_calibrated_pairwise_backup",
                    lambda r: _abstain_pred(r, str(args.primary_calibration)),
                    lambda r: _fallback("pairwise_binary_backup", r) if _abstain_pred(r, str(args.primary_calibration)) is None else int(_abstain_pred(r, str(args.primary_calibration)) or 0),
                    str(args.primary_calibration),
                    "pairwise_binary_backup",
                ),
                (
                    "near_tie_policy_pairwise_backup",
                    lambda r: _near_tie_policy_decision(r, "pairwise_binary_backup"),
                    lambda r: _near_tie_policy_decision(r, "pairwise_binary_backup"),
                    str(args.primary_calibration),
                    "pairwise_binary_backup",
                ),
                (
                    "near_tie_policy_pointwise_value",
                    lambda r: _near_tie_policy_decision(r, "pointwise_value"),
                    lambda r: _near_tie_policy_decision(r, "pointwise_value"),
                    str(args.primary_calibration),
                    "pointwise_value",
                ),
                (
                    "near_tie_policy_balanced_shared",
                    lambda r: _near_tie_policy_decision(r, "balanced_round_robin"),
                    lambda r: _near_tie_policy_decision(r, "balanced_round_robin"),
                    str(args.primary_calibration),
                    "balanced_round_robin",
                ),
                (
                    "near_tie_policy_score_gap_heuristic",
                    lambda r: _near_tie_policy_decision(r, "score_gap_heuristic"),
                    lambda r: _near_tie_policy_decision(r, "score_gap_heuristic"),
                    str(args.primary_calibration),
                    "score_gap_heuristic",
                ),
            ]

            test_rows = [r for r in tables["pairwise"] if str(r.get("split")) == "test"]
            near_tie_decisions = [_is_near_tie(r)[0] for r in test_rows]
            detector_stats = {
                "test_pairs": len(test_rows),
                "detected_near_ties": int(sum(int(v) for v in near_tie_decisions)),
                "detected_rate": float(sum(int(v) for v in near_tie_decisions) / max(1, len(test_rows))),
                "on_supervised_near_tie_slice": float(
                    sum(int(_is_near_tie(r)[0]) for r in test_rows if bool(r.get("near_tie_flag", False)))
                    / max(1, sum(int(bool(r.get("near_tie_flag", False))) for r in test_rows))
                ),
            }

            seed_payload: dict[str, Any] = {
                "calibration_fit": {
                    "split": calibrators.get("split"),
                    "n_val": calibrators.get("n_val"),
                    "methods": {k: {kk: vv for kk, vv in v.items() if kk != "model"} for k, v in calibrators.get("methods", {}).items()},
                },
                "calibration_test": calibration_eval,
                "near_tie_detector": {"config": detector_cfg, "stats": detector_stats},
                "variants": {},
            }

            for vname, pred_fn, forced_fn, calib_name, fallback_name in variants:
                met = _evaluate_formulation(tables["pairwise"], decision_fn=pred_fn, forced_fn=forced_fn)
                top1 = _top1_from_decisions(tables["pairwise"], tables["state_to_candidates"], pred_fn, forced_fn)
                by_budget = _slice_acc(tables["pairwise"], forced_fn, lambda r: str(int(r.get("remaining_budget", 0))))
                by_dataset = _slice_acc(tables["pairwise"], forced_fn, lambda r: str(r.get("dataset_name", "unknown")))
                near_test_rows = [r for r in test_rows if _is_near_tie(r)[0]]
                non_near_test_rows = [r for r in test_rows if not _is_near_tie(r)[0]]
                near_det_acc = (
                    sum(int(forced_fn(r) == int(r.get("label", 0))) for r in near_test_rows) / max(1, len(near_test_rows))
                )
                non_near_det_acc = (
                    sum(int(forced_fn(r) == int(r.get("label", 0))) for r in non_near_test_rows) / max(1, len(non_near_test_rows))
                )
                seed_payload["variants"][vname] = {
                    "calibration": calib_name,
                    "fallback_policy": fallback_name,
                    **met,
                    "top1_test": float(top1),
                    "detected_near_tie_forced_accuracy": float(near_det_acc),
                    "non_detected_forced_accuracy": float(non_near_det_acc),
                    "forced_accuracy_by_budget": by_budget,
                    "forced_accuracy_by_dataset": by_dataset,
                }
                summary_rows.append(
                    {
                        "regime": regime,
                        "seed": seed,
                        "variant": vname,
                        "calibration": calib_name,
                        "fallback_policy": fallback_name,
                        **met,
                        "top1_test": float(top1),
                        "detected_near_tie_forced_accuracy": float(near_det_acc),
                        "non_detected_forced_accuracy": float(non_near_det_acc),
                    }
                )
            detailed["results"][regime][str(seed)] = seed_payload

    (out_dir / "near_tie_policy_results.json").write_text(json.dumps(detailed, indent=2), encoding="utf-8")
    (out_dir / "near_tie_policy_summary.json").write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")

    md = [
        "# Dedicated near-tie policy matched experiment",
        "",
        f"- targets_root: `{args.targets_root}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        f"- feature_set: `{args.feature_set}`",
        f"- primary_calibration: `{args.primary_calibration}`",
        f"- near_tie_detector_config: `{json.dumps(detector_cfg, sort_keys=True)}`",
        "",
    ]
    for regime in sorted(set(r["regime"] for r in summary_rows)):
        md.append(f"## Regime `{regime}`")
        rows_regime = [r for r in summary_rows if r["regime"] == regime]
        for vname in sorted(set(r["variant"] for r in rows_regime)):
            rows = [r for r in rows_regime if r["variant"] == vname]
            md.append(
                f"- {vname}: accepted_acc={_mean([x['accepted_pair_accuracy'] for x in rows]):.4f}, "
                f"coverage={_mean([x['coverage'] for x in rows]):.4f}, "
                f"forced_acc={_mean([x['forced_pairwise_accuracy'] for x in rows]):.4f}, "
                f"near_tie_forced={_mean([x['near_tie_forced_accuracy'] for x in rows]):.4f}, "
                f"adjacent_forced={_mean([x['adjacent_forced_accuracy'] for x in rows]):.4f}, "
                f"top1={_mean([x['top1_test'] for x in rows]):.4f}"
            )
        md.append("")
    (out_dir / "near_tie_policy_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir), "rows": len(summary_rows)}, indent=2))


if __name__ == "__main__":
    main()
