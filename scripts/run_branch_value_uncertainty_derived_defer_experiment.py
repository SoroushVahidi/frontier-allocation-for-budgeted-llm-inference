#!/usr/bin/env python3
"""Bounded branch-value + uncertainty experiment with derived compare/defer decisions.

This script intentionally keeps pairwise winner labels as an evaluation target, not the
primary supervised target. Primary supervision is branch-level value prediction
(estimated_value_if_allocate_next) with an auxiliary residual-risk head.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    _sigmoid,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Branch-value + uncertainty derived compare/defer experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", choices=["v1", "v2", "v3"], default="v2")
    p.add_argument("--pointwise-alpha", type=float, default=1.0)
    p.add_argument("--uncertainty-alpha", type=float, default=1.0)
    p.add_argument("--coverage-floor", type=float, default=0.55)
    p.add_argument("--threshold-grid-gap", default="0.00,0.01,0.02,0.03,0.05,0.08")
    p.add_argument("--threshold-grid-z", default="0.25,0.50,0.75,1.00,1.25,1.50")
    p.add_argument("--outside-gap-threshold", type=float, default=0.03)
    p.add_argument("--outside-z-max", type=float, default=1.0)
    return p.parse_args()


def _parse_csv_floats(text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    return vals if vals else [0.0]


def _safe_mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _fit_pointwise_value(candidates: list[dict[str, Any]], *, alpha: float) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    model = Ridge(alpha=float(alpha), random_state=0)
    model.fit(x, y)
    return {
        "status": "ok",
        "model": model,
        "training_rows": len(train),
        "target": "estimated_value_if_allocate_next",
    }


def _predict_value(model_obj: dict[str, Any], row: dict[str, Any]) -> float:
    if str(model_obj.get("status")) != "ok":
        return float(row.get("estimated_value_if_allocate_next", 0.0))
    model: Ridge = model_obj["model"]
    return float(model.predict(np.array([row["x"]], dtype=float))[0])


def _fit_uncertainty_head(candidates: list[dict[str, Any]], value_model_obj: dict[str, Any], *, alpha: float) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}

    x = np.array([r["x"] for r in train], dtype=float)
    value_preds = np.array([_predict_value(value_model_obj, r) for r in train], dtype=float)
    y_true = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    base_std = np.array([float(r.get("allocation_value_std", 0.0)) for r in train], dtype=float)
    residual_target = np.abs(y_true - value_preds)
    y = np.maximum(residual_target, 0.20 * base_std)

    model = Ridge(alpha=float(alpha), random_state=0)
    model.fit(x, y)

    return {
        "status": "ok",
        "model": model,
        "training_rows": len(train),
        "target": "abs_residual_value_error_proxy",
        "notes": "Residual-risk head predicts branch-level error scale; combined with allocation_value_std at inference.",
    }


def _predict_branch_sigma(unc_model_obj: dict[str, Any], row: dict[str, Any]) -> float:
    base_std = float(row.get("allocation_value_std", 0.0))
    if str(unc_model_obj.get("status")) != "ok":
        return max(1e-6, base_std)
    model: Ridge = unc_model_obj["model"]
    residual_scale = float(model.predict(np.array([row["x"]], dtype=float))[0])
    residual_scale = max(0.0, residual_scale)
    return max(1e-6, 0.5 * base_std + 0.5 * residual_scale)


def _pair_prediction(row: dict[str, Any], *, gap_threshold: float, z_threshold: float, outside_gap_threshold: float, outside_z_max: float) -> dict[str, Any]:
    vi = float(row.get("pred_value_i", 0.0))
    vj = float(row.get("pred_value_j", 0.0))
    si = max(1e-6, float(row.get("pred_sigma_i", 0.0)))
    sj = max(1e-6, float(row.get("pred_sigma_j", 0.0)))
    diff = vi - vj
    abs_gap = abs(diff)
    pair_sigma = float(np.sqrt(si * si + sj * sj))
    z_gap = abs_gap / max(1e-6, pair_sigma)
    outside_gap = float(row.get("pair_best_vs_outside_gap", 0.0))

    defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
    if outside_gap <= outside_gap_threshold and z_gap <= outside_z_max:
        defer = True
    if defer:
        action = None
    else:
        action = 1 if diff >= 0.0 else 0

    return {
        "action": action,
        "pred_diff": diff,
        "pred_abs_gap": abs_gap,
        "pred_pair_sigma": pair_sigma,
        "pred_gap_z": z_gap,
        "outside_gap": outside_gap,
    }


def _evaluate_rows(rows: list[dict[str, Any]], *, gap_threshold: float, z_threshold: float, outside_gap_threshold: float, outside_z_max: float, split: str) -> dict[str, float]:
    subset = [r for r in rows if str(r.get("split")) == split]
    accepted: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for r in subset:
        pred = _pair_prediction(
            r,
            gap_threshold=gap_threshold,
            z_threshold=z_threshold,
            outside_gap_threshold=outside_gap_threshold,
            outside_z_max=outside_z_max,
        )
        r["_pred"] = pred
        if pred["action"] is None:
            deferred.append(r)
        else:
            accepted.append(r)

    def _acc(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        return sum(int(int(r["_pred"]["action"]) == int(r.get("label", 0))) for r in items if r["_pred"]["action"] is not None) / max(1, sum(1 for r in items if r["_pred"]["action"] is not None))

    def _forced_acc(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        return sum(int((1 if float(r["_pred"]["pred_diff"]) >= 0.0 else 0) == int(r.get("label", 0))) for r in items) / len(items)

    near = [r for r in subset if bool(r.get("near_tie_flag", False))]
    adjacent = [r for r in subset if str(r.get("pair_type", "")) == "adjacent_rank"]

    def _slice_acc(items: list[dict[str, Any]]) -> float:
        items_acc = [r for r in items if r["_pred"]["action"] is not None]
        if not items_acc:
            return 0.0
        return sum(int(int(r["_pred"]["action"]) == int(r.get("label", 0))) for r in items_acc) / len(items_acc)

    budgets = sorted({int(float(r.get("remaining_budget", 0.0))) for r in subset})
    budget_slice: dict[str, dict[str, float]] = {}
    for b in budgets:
        b_rows = [r for r in subset if int(float(r.get("remaining_budget", 0.0))) == b]
        b_acc = [r for r in b_rows if r["_pred"]["action"] is not None]
        budget_slice[str(b)] = {
            "coverage": len(b_acc) / max(1, len(b_rows)),
            "accepted_pair_accuracy": _acc(b_acc),
            "rows": float(len(b_rows)),
        }

    return {
        "accepted_pair_accuracy": _acc(accepted),
        "coverage": len(accepted) / max(1, len(subset)),
        "defer_rate": len(deferred) / max(1, len(subset)),
        "forced_accuracy_on_deferred": _forced_acc(deferred),
        "near_tie_accepted_pair_accuracy": _slice_acc(near),
        "adjacent_rank_accepted_pair_accuracy": _slice_acc(adjacent),
        "accepted_mean_true_value_gap": _safe_mean([float(r.get("pair_value_gap", 0.0)) for r in accepted]),
        "deferred_mean_true_value_gap": _safe_mean([float(r.get("pair_value_gap", 0.0)) for r in deferred]),
        "accepted_mean_gap_z": _safe_mean([float(r["_pred"]["pred_gap_z"]) for r in accepted]),
        "deferred_mean_gap_z": _safe_mean([float(r["_pred"]["pred_gap_z"]) for r in deferred]),
        "accepted_mean_pair_oracle_defer_score": _safe_mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in accepted]),
        "deferred_mean_pair_oracle_defer_score": _safe_mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in deferred]),
        "test_pairs": float(len(subset)),
        "budget_slices": budget_slice,
    }


def _evaluate_pairwise_baseline(rows: list[dict[str, Any]], *, pairwise_model: dict[str, Any], split: str) -> dict[str, float]:
    subset = [r for r in rows if str(r.get("split")) == split]
    if not subset:
        return {"accuracy": 0.0, "coverage": 0.0, "test_pairs": 0.0}

    if str(pairwise_model.get("status")) == "ok":
        w = np.array(pairwise_model.get("weights", []), dtype=float)
        b = float(pairwise_model.get("intercept", 0.0))

        def _pred(rr: dict[str, Any]) -> int:
            z = float(np.dot(w, np.array(rr["x_diff"], dtype=float)) + b)
            return 1 if _sigmoid(z) >= 0.5 else 0

    else:
        const = int(pairwise_model.get("constant_label", 0))

        def _pred(_rr: dict[str, Any]) -> int:
            return const

    acc = sum(int(_pred(r) == int(r.get("label", 0))) for r in subset) / len(subset)
    near = [r for r in subset if bool(r.get("near_tie_flag", False))]
    adjacent = [r for r in subset if str(r.get("pair_type", "")) == "adjacent_rank"]

    return {
        "accepted_pair_accuracy": float(acc),
        "coverage": 1.0,
        "defer_rate": 0.0,
        "near_tie_accepted_pair_accuracy": (
            sum(int(_pred(r) == int(r.get("label", 0))) for r in near) / len(near) if near else 0.0
        ),
        "adjacent_rank_accepted_pair_accuracy": (
            sum(int(_pred(r) == int(r.get("label", 0))) for r in adjacent) / len(adjacent) if adjacent else 0.0
        ),
        "test_pairs": float(len(subset)),
    }


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    regimes = [x.strip() for x in str(args.regimes).split(",") if x.strip()]
    gap_grid = _parse_csv_floats(args.threshold_grid_gap)
    z_grid = _parse_csv_floats(args.threshold_grid_z)

    run_dir = Path(args.output_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    config = {
        "targets_root": args.targets_root,
        "run_id": args.run_id,
        "regimes": regimes,
        "seeds": seeds,
        "feature_set": args.feature_set,
        "pointwise_alpha": args.pointwise_alpha,
        "uncertainty_alpha": args.uncertainty_alpha,
        "coverage_floor": args.coverage_floor,
        "threshold_grid_gap": gap_grid,
        "threshold_grid_z": z_grid,
        "outside_gap_threshold": args.outside_gap_threshold,
        "outside_z_max": args.outside_z_max,
        "value_target": "estimated_value_if_allocate_next",
        "uncertainty_signals": [
            "allocation_value_std",
            "mode_exact/mode_approx provenance features",
            "residual-risk head (abs residual proxy)",
            "pair_best_vs_outside_gap",
        ],
    }

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            raise FileNotFoundError(f"Missing regime directory: {regime_dir}")

        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                feature_set=args.feature_set,
                pointwise_alpha=args.pointwise_alpha,
                train_pairwise=True,
                train_pointwise=False,
                train_outside_option=False,
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                train_pairwise_svm=False,
            )
            artifacts = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(artifacts, cfg)
            pair_rows = tables["pairwise"]
            candidates = tables["candidates"]

            value_model = _fit_pointwise_value(candidates, alpha=args.pointwise_alpha)
            unc_model = _fit_uncertainty_head(candidates, value_model, alpha=args.uncertainty_alpha)

            candidate_lookup = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
            for r in pair_rows:
                key_i = (str(r["state_id"]), str(r["branch_i"]))
                key_j = (str(r["state_id"]), str(r["branch_j"]))
                ci = candidate_lookup[key_i]
                cj = candidate_lookup[key_j]
                r["pred_value_i"] = _predict_value(value_model, ci)
                r["pred_value_j"] = _predict_value(value_model, cj)
                r["pred_sigma_i"] = _predict_branch_sigma(unc_model, ci)
                r["pred_sigma_j"] = _predict_branch_sigma(unc_model, cj)

            best_sel: dict[str, Any] | None = None
            for g in gap_grid:
                for z in z_grid:
                    val_metrics = _evaluate_rows(
                        pair_rows,
                        gap_threshold=float(g),
                        z_threshold=float(z),
                        outside_gap_threshold=float(args.outside_gap_threshold),
                        outside_z_max=float(args.outside_z_max),
                        split="val",
                    )
                    if val_metrics["coverage"] < float(args.coverage_floor):
                        continue
                    score = val_metrics["accepted_pair_accuracy"]
                    cand = {"gap_threshold": float(g), "z_threshold": float(z), "val": val_metrics, "score": score}
                    if best_sel is None or float(cand["score"]) > float(best_sel["score"]):
                        best_sel = cand
            if best_sel is None:
                fallback = {"gap_threshold": 0.0, "z_threshold": 0.0}
            else:
                fallback = {"gap_threshold": float(best_sel["gap_threshold"]), "z_threshold": float(best_sel["z_threshold"])}

            final_metrics = _evaluate_rows(
                pair_rows,
                gap_threshold=float(fallback["gap_threshold"]),
                z_threshold=float(fallback["z_threshold"]),
                outside_gap_threshold=float(args.outside_gap_threshold),
                outside_z_max=float(args.outside_z_max),
                split="test",
            )

            baseline_models = train_models(
                tables,
                LearningConfig(
                    seed=seed,
                    feature_set=args.feature_set,
                    train_pairwise=True,
                    train_pointwise=False,
                    train_outside_option=False,
                    train_lightgbm_ranker=False,
                    train_catboost_ranker=False,
                    train_pairwise_svm=False,
                ),
            )
            pairwise_baseline = _evaluate_pairwise_baseline(
                pair_rows,
                pairwise_model=baseline_models.get("pairwise", {}),
                split="test",
            )

            value_only_no_defer = _evaluate_rows(
                pair_rows,
                gap_threshold=0.0,
                z_threshold=0.0,
                outside_gap_threshold=-1e9,
                outside_z_max=-1e9,
                split="test",
            )

            row = {
                "regime": regime,
                "seed": seed,
                "selected_thresholds": fallback,
                "value_target": "estimated_value_if_allocate_next",
                "uncertainty_head": {
                    "type": "ridge_residual_proxy",
                    "status": unc_model.get("status", "unknown"),
                },
                "derived_value_uncertainty_defer": final_metrics,
                "baseline_pairwise_binary": pairwise_baseline,
                "baseline_value_only_forced": {
                    "accepted_pair_accuracy": value_only_no_defer["accepted_pair_accuracy"],
                    "coverage": value_only_no_defer["coverage"],
                    "defer_rate": value_only_no_defer["defer_rate"],
                    "near_tie_accepted_pair_accuracy": value_only_no_defer["near_tie_accepted_pair_accuracy"],
                    "adjacent_rank_accepted_pair_accuracy": value_only_no_defer["adjacent_rank_accepted_pair_accuracy"],
                    "test_pairs": value_only_no_defer["test_pairs"],
                },
            }
            all_rows.append(row)

    summary: dict[str, Any] = {"rows": all_rows}
    by_variant: dict[str, list[float]] = {
        "derived_accuracy": [],
        "derived_coverage": [],
        "derived_defer_rate": [],
        "pairwise_accuracy": [],
        "value_forced_accuracy": [],
        "near_tie_derived_accuracy": [],
        "adjacent_derived_accuracy": [],
    }
    for r in all_rows:
        d = r["derived_value_uncertainty_defer"]
        p = r["baseline_pairwise_binary"]
        v = r["baseline_value_only_forced"]
        by_variant["derived_accuracy"].append(float(d["accepted_pair_accuracy"]))
        by_variant["derived_coverage"].append(float(d["coverage"]))
        by_variant["derived_defer_rate"].append(float(d["defer_rate"]))
        by_variant["pairwise_accuracy"].append(float(p["accepted_pair_accuracy"]))
        by_variant["value_forced_accuracy"].append(float(v["accepted_pair_accuracy"]))
        by_variant["near_tie_derived_accuracy"].append(float(d["near_tie_accepted_pair_accuracy"]))
        by_variant["adjacent_derived_accuracy"].append(float(d["adjacent_rank_accepted_pair_accuracy"]))

    aggregate = {k: _safe_mean(v) for k, v in by_variant.items()}
    aggregate["paired_delta_accuracy_vs_pairwise"] = aggregate["derived_accuracy"] - aggregate["pairwise_accuracy"]
    aggregate["paired_delta_accuracy_vs_value_forced"] = aggregate["derived_accuracy"] - aggregate["value_forced_accuracy"]
    summary["aggregate"] = aggregate

    (run_dir / "value_uncertainty_compare_defer_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (run_dir / "value_uncertainty_compare_defer_results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (run_dir / "value_uncertainty_compare_defer_manifest.json").write_text(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "artifacts": [
                    "value_uncertainty_compare_defer_config.json",
                    "value_uncertainty_compare_defer_results.json",
                    "value_uncertainty_compare_defer_summary.json",
                    "value_uncertainty_compare_defer_manifest.json",
                ],
                "invocation": "python scripts/run_branch_value_uncertainty_derived_defer_experiment.py --targets-root <targets_root> --run-id <run_id>",
                "notes": [
                    "Primary supervision is branch-level value target + residual-risk uncertainty head.",
                    "Pairwise winner prediction is derived from value gap and uncertainty-adjusted defer gating.",
                ],
                "assumptions": [
                    "estimated_value_if_allocate_next is a proxy for budget-conditioned branch continuation value.",
                    "allocation_value_std and residual-risk head together approximate predictive uncertainty.",
                ],
                "caveats": [
                    "Thresholds are selected on validation split with a coverage floor.",
                    "This script is bounded and does not claim final canonical replacement.",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary_brief = {
        "run_id": args.run_id,
        "targets_root": args.targets_root,
        "aggregate": aggregate,
        "assumptions": {
            "value_target": "estimated_value_if_allocate_next as budget-conditioned branch-value proxy",
            "uncertainty": "allocation_value_std + residual-risk head",
            "defer_rule": "defer when low absolute gap or low gap-z or outside-option is competitive under low-confidence",
        },
        "caveats": [
            "This is a bounded experiment pass, not a full canonical replacement.",
            "Pairwise baselines are limited to in-repo runnable baselines available from the same target artifacts.",
        ],
    }
    (run_dir / "value_uncertainty_compare_defer_summary.json").write_text(json.dumps(summary_brief, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary_brief, indent=2))


if __name__ == "__main__":
    main()
