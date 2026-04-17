#!/usr/bin/env python3
"""Strict validation pass for branch-value + uncertainty derived compare/defer method.

Runs bounded ablations on available target regimes and writes machine-readable summaries.
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

from experiments.bruteforce_branch_allocator import LearningConfig, _sigmoid, load_label_artifacts, prepare_learning_tables, train_models  # noqa: E402


ABLATION_ORDER = [
    "value_only",
    "value_raw_uncertainty",
    "value_learned_risk",
    "value_outside_option",
    "full_method",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Strict validation for branch-value uncertainty method")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--coverage-floor", type=float, default=0.55)
    p.add_argument("--threshold-grid-gap", default="0.00,0.01,0.02,0.03,0.05,0.08")
    p.add_argument("--threshold-grid-z", default="0.25,0.50,0.75,1.00,1.25,1.50")
    p.add_argument("--outside-gap-threshold", type=float, default=0.03)
    p.add_argument("--oracle-defer-score-threshold", type=float, default=2.0)
    return p.parse_args()


def _parse_csv_floats(text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    return vals if vals else [0.0]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _fit_value(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    m = Ridge(alpha=1.0, random_state=0)
    m.fit(x, y)
    return {"status": "ok", "model": m, "training_rows": len(train)}


def _pred_value(model_obj: dict[str, Any], row: dict[str, Any]) -> float:
    if str(model_obj.get("status")) != "ok":
        return float(row.get("estimated_value_if_allocate_next", 0.0))
    m: Ridge = model_obj["model"]
    return float(m.predict(np.array([row["x"]], dtype=float))[0])


def _fit_risk(candidates: list[dict[str, Any]], value_model: dict[str, Any]) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    yp = np.array([_pred_value(value_model, r) for r in train], dtype=float)
    yt = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    raw = np.array([float(r.get("allocation_value_std", 0.0)) for r in train], dtype=float)
    y = np.maximum(np.abs(yt - yp), 0.2 * raw)
    m = Ridge(alpha=1.0, random_state=0)
    m.fit(x, y)
    return {"status": "ok", "model": m, "training_rows": len(train)}


def _pred_learned_sigma(risk_model: dict[str, Any], row: dict[str, Any]) -> float:
    raw = float(row.get("allocation_value_std", 0.0))
    if str(risk_model.get("status")) != "ok":
        return max(1e-6, raw)
    m: Ridge = risk_model["model"]
    learned = max(0.0, float(m.predict(np.array([row["x"]], dtype=float))[0]))
    return max(1e-6, learned)


def _apply_variant(
    row: dict[str, Any],
    *,
    variant: str,
    gap_threshold: float,
    z_threshold: float,
    outside_gap_threshold: float,
) -> dict[str, Any]:
    diff = float(row.get("pred_value_i", 0.0)) - float(row.get("pred_value_j", 0.0))
    abs_gap = abs(diff)
    raw_si = float(row.get("raw_sigma_i", 0.0))
    raw_sj = float(row.get("raw_sigma_j", 0.0))
    lr_si = float(row.get("learned_sigma_i", 0.0))
    lr_sj = float(row.get("learned_sigma_j", 0.0))
    outside_gap = float(row.get("pair_best_vs_outside_gap", 0.0))

    if variant == "value_only":
        action = 1 if diff >= 0.0 else 0
        defer = False
        z_gap = 9e9
    elif variant == "value_raw_uncertainty":
        pair_sigma = float(np.sqrt(raw_si * raw_si + raw_sj * raw_sj))
        z_gap = abs_gap / max(1e-6, pair_sigma)
        defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
        action = None if defer else (1 if diff >= 0.0 else 0)
    elif variant == "value_learned_risk":
        pair_sigma = float(np.sqrt(lr_si * lr_si + lr_sj * lr_sj))
        z_gap = abs_gap / max(1e-6, pair_sigma)
        defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
        action = None if defer else (1 if diff >= 0.0 else 0)
    elif variant == "value_outside_option":
        z_gap = 0.0
        defer = (abs_gap < gap_threshold) or (outside_gap <= outside_gap_threshold)
        action = None if defer else (1 if diff >= 0.0 else 0)
    else:  # full_method
        pair_sigma = float(np.sqrt((0.5 * raw_si + 0.5 * lr_si) ** 2 + (0.5 * raw_sj + 0.5 * lr_sj) ** 2))
        z_gap = abs_gap / max(1e-6, pair_sigma)
        defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
        if outside_gap <= outside_gap_threshold and z_gap <= z_threshold:
            defer = True
        action = None if defer else (1 if diff >= 0.0 else 0)

    return {"action": action, "defer": bool(defer), "z_gap": float(z_gap), "abs_gap": float(abs_gap), "outside_gap": outside_gap, "diff": diff}


def _metrics(rows: list[dict[str, Any]], *, variant: str, gap_threshold: float, z_threshold: float, outside_gap_threshold: float, split: str) -> dict[str, Any]:
    subset = [r for r in rows if str(r.get("split")) == split]
    accepted = []
    deferred = []
    for r in subset:
        p = _apply_variant(r, variant=variant, gap_threshold=gap_threshold, z_threshold=z_threshold, outside_gap_threshold=outside_gap_threshold)
        if p["action"] is None:
            deferred.append((r, p))
        else:
            accepted.append((r, p))

    def _acc(items: list[tuple[dict[str, Any], dict[str, Any]]]) -> float:
        if not items:
            return 0.0
        return sum(int(int(pp["action"]) == int(rr.get("label", 0))) for rr, pp in items) / len(items)

    near = [(r, p) for (r, p) in accepted if bool(r.get("near_tie_flag", False))]
    adj = [(r, p) for (r, p) in accepted if str(r.get("pair_type", "")) == "adjacent_rank"]

    budget: dict[str, dict[str, float]] = {}
    for b in sorted({int(float(r.get("remaining_budget", 0.0))) for r in subset}):
        b_all = [(r, _apply_variant(r, variant=variant, gap_threshold=gap_threshold, z_threshold=z_threshold, outside_gap_threshold=outside_gap_threshold)) for r in subset if int(float(r.get("remaining_budget", 0.0))) == b]
        b_acc = [(r, p) for r, p in b_all if p["action"] is not None]
        budget[str(b)] = {
            "coverage": len(b_acc) / max(1, len(b_all)),
            "accepted_pair_accuracy": _acc(b_acc),
            "rows": float(len(b_all)),
        }

    dataset: dict[str, dict[str, float]] = {}
    for ds in sorted({str(r.get("dataset_name", "unknown")) for r in subset}):
        ds_all = [(r, _apply_variant(r, variant=variant, gap_threshold=gap_threshold, z_threshold=z_threshold, outside_gap_threshold=outside_gap_threshold)) for r in subset if str(r.get("dataset_name", "unknown")) == ds]
        ds_acc = [(r, p) for r, p in ds_all if p["action"] is not None]
        dataset[ds] = {
            "coverage": len(ds_acc) / max(1, len(ds_all)),
            "accepted_pair_accuracy": _acc(ds_acc),
            "rows": float(len(ds_all)),
        }

    return {
        "accepted_pair_accuracy": _acc(accepted),
        "coverage": len(accepted) / max(1, len(subset)),
        "defer_rate": len(deferred) / max(1, len(subset)),
        "near_tie_accepted_pair_accuracy": _acc(near),
        "adjacent_rank_accepted_pair_accuracy": _acc(adj),
        "accepted_mean_true_value_gap": _mean([float(r.get("pair_value_gap", 0.0)) for r, _ in accepted]),
        "deferred_mean_true_value_gap": _mean([float(r.get("pair_value_gap", 0.0)) for r, _ in deferred]),
        "accepted_mean_pair_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r, _ in accepted]),
        "deferred_mean_pair_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r, _ in deferred]),
        "forced_accuracy_on_deferred": (
            sum(int((1 if p["diff"] >= 0.0 else 0) == int(r.get("label", 0))) for r, p in deferred) / len(deferred)
            if deferred
            else 0.0
        ),
        "test_pairs": float(len(subset)),
        "budget_slices": budget,
        "dataset_slices": dataset,
    }


def _pairwise_baseline(rows: list[dict[str, Any]], model: dict[str, Any], split: str) -> dict[str, float]:
    subset = [r for r in rows if str(r.get("split")) == split]
    if not subset:
        return {"accepted_pair_accuracy": 0.0, "coverage": 0.0, "defer_rate": 0.0}
    if str(model.get("status")) == "ok":
        w = np.array(model.get("weights", []), dtype=float)
        b = float(model.get("intercept", 0.0))

        def _pred(r: dict[str, Any]) -> int:
            z = float(np.dot(w, np.array(r["x_diff"], dtype=float)) + b)
            return 1 if _sigmoid(z) >= 0.5 else 0

    else:
        c = int(model.get("constant_label", 0))

        def _pred(_r: dict[str, Any]) -> int:
            return c
    return {
        "accepted_pair_accuracy": sum(int(_pred(r) == int(r.get("label", 0))) for r in subset) / len(subset),
        "coverage": 1.0,
        "defer_rate": 0.0,
        "near_tie_accepted_pair_accuracy": (
            sum(int(_pred(r) == int(r.get("label", 0))) for r in subset if bool(r.get("near_tie_flag", False)))
            / max(1, sum(1 for r in subset if bool(r.get("near_tie_flag", False))))
        ),
        "adjacent_rank_accepted_pair_accuracy": (
            sum(int(_pred(r) == int(r.get("label", 0))) for r in subset if str(r.get("pair_type", "")) == "adjacent_rank")
            / max(1, sum(1 for r in subset if str(r.get("pair_type", "")) == "adjacent_rank"))
        ),
        "test_pairs": float(len(subset)),
    }


def _penalized_proxy_baseline(rows: list[dict[str, Any]], *, split: str, oracle_defer_score_threshold: float) -> dict[str, float]:
    subset = [r for r in rows if str(r.get("split")) == split]
    acc_n = 0
    n_acc = 0
    n_def = 0
    for r in subset:
        # Important: avoid directional label leakage from ternary_defer_label.
        # We only use defer/not-defer as proxy signal; direction still comes from model value diff.
        if "ternary_defer_label" in r:
            td = int(r.get("ternary_defer_label", 1))
            defer = td == 1
        else:
            defer = float(r.get("pair_oracle_defer_score", 0.0)) >= oracle_defer_score_threshold

        if defer:
            n_def += 1
            continue

        n_acc += 1
        pred = 1 if float(r.get("pred_value_i", 0.0)) >= float(r.get("pred_value_j", 0.0)) else 0
        acc_n += int(pred == int(r.get("label", 0)))

    return {
        "accepted_pair_accuracy": (acc_n / n_acc) if n_acc else 0.0,
        "coverage": n_acc / max(1, len(subset)),
        "defer_rate": n_def / max(1, len(subset)),
        "test_pairs": float(len(subset)),
        "notes": "Proxy-only comparable baseline: defer from ternary_defer_label (if present) or pair_oracle_defer_score threshold; direction from model value difference.",
    }


def _load_reference_strong_baseline() -> dict[str, Any]:
    p = Path("outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/near_tie_pointwise_expert_summary.json")
    if not p.exists():
        return {"status": "missing"}
    d = json.loads(p.read_text())
    return {"status": "ok", "source": str(p), "summary": d}


def main() -> None:
    args = parse_args()
    run_dir = Path(args.output_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    regimes = [x.strip() for x in str(args.regimes).split(",") if x.strip()]
    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    gap_grid = _parse_csv_floats(args.threshold_grid_gap)
    z_grid = _parse_csv_floats(args.threshold_grid_z)

    rows_out: list[dict[str, Any]] = []
    missing_regimes: list[str] = []

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            missing_regimes.append(str(regime_dir))
            continue

        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                feature_set=args.feature_set,
                train_pairwise=True,
                train_pointwise=False,
                train_outside_option=False,
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                train_pairwise_svm=False,
            )
            tables = prepare_learning_tables(load_label_artifacts(regime_dir), cfg)
            state_to_dataset = tables.get("state_to_dataset", {})
            pair_rows = tables["pairwise"]
            candidates = tables["candidates"]

            cand_lookup = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
            value_model = _fit_value(candidates)
            risk_model = _fit_risk(candidates, value_model)

            for r in pair_rows:
                ci = cand_lookup[(str(r["state_id"]), str(r["branch_i"]))]
                cj = cand_lookup[(str(r["state_id"]), str(r["branch_j"]))]
                r["dataset_name"] = str(state_to_dataset.get(str(r["state_id"]), "unknown"))
                r["pred_value_i"] = _pred_value(value_model, ci)
                r["pred_value_j"] = _pred_value(value_model, cj)
                r["raw_sigma_i"] = max(1e-6, float(ci.get("allocation_value_std", 0.0)))
                r["raw_sigma_j"] = max(1e-6, float(cj.get("allocation_value_std", 0.0)))
                r["learned_sigma_i"] = _pred_learned_sigma(risk_model, ci)
                r["learned_sigma_j"] = _pred_learned_sigma(risk_model, cj)

            variant_metrics: dict[str, Any] = {}
            selected_thresholds: dict[str, Any] = {}
            for variant in ABLATION_ORDER:
                if variant == "value_only":
                    sel = {"gap_threshold": 0.0, "z_threshold": 0.0}
                else:
                    best = None
                    for g in gap_grid:
                        for z in z_grid:
                            m_val = _metrics(pair_rows, variant=variant, gap_threshold=g, z_threshold=z, outside_gap_threshold=float(args.outside_gap_threshold), split="val")
                            if float(m_val["coverage"]) < float(args.coverage_floor):
                                continue
                            candidate = {"gap_threshold": g, "z_threshold": z, "score": float(m_val["accepted_pair_accuracy"]), "val": m_val}
                            if best is None or candidate["score"] > best["score"]:
                                best = candidate
                    if best is None:
                        sel = {"gap_threshold": 0.0, "z_threshold": 0.0}
                    else:
                        sel = {"gap_threshold": float(best["gap_threshold"]), "z_threshold": float(best["z_threshold"])}
                selected_thresholds[variant] = sel
                variant_metrics[variant] = _metrics(
                    pair_rows,
                    variant=variant,
                    gap_threshold=float(sel["gap_threshold"]),
                    z_threshold=float(sel["z_threshold"]),
                    outside_gap_threshold=float(args.outside_gap_threshold),
                    split="test",
                )

            trained = train_models(tables, cfg)
            pairwise_base = _pairwise_baseline(pair_rows, trained.get("pairwise", {}), split="test")
            penalized_proxy = _penalized_proxy_baseline(pair_rows, split="test", oracle_defer_score_threshold=float(args.oracle_defer_score_threshold))

            rows_out.append(
                {
                    "regime": regime,
                    "seed": seed,
                    "variant_metrics": variant_metrics,
                    "selected_thresholds": selected_thresholds,
                    "pairwise_binary_baseline": pairwise_base,
                    "penalized_marginal_proxy_baseline": penalized_proxy,
                    "risk_head_status": str(risk_model.get("status", "unknown")),
                }
            )

    agg: dict[str, Any] = {"variants": {}, "pairwise_binary_baseline": {}, "penalized_marginal_proxy_baseline": {}}
    for variant in ABLATION_ORDER:
        v_rows = [r["variant_metrics"][variant] for r in rows_out if variant in r.get("variant_metrics", {})]
        agg["variants"][variant] = {
            "accepted_pair_accuracy": _mean([float(x["accepted_pair_accuracy"]) for x in v_rows]),
            "coverage": _mean([float(x["coverage"]) for x in v_rows]),
            "defer_rate": _mean([float(x["defer_rate"]) for x in v_rows]),
            "near_tie_accepted_pair_accuracy": _mean([float(x["near_tie_accepted_pair_accuracy"]) for x in v_rows]),
            "adjacent_rank_accepted_pair_accuracy": _mean([float(x["adjacent_rank_accepted_pair_accuracy"]) for x in v_rows]),
        }

    p_rows = [r["pairwise_binary_baseline"] for r in rows_out]
    q_rows = [r["penalized_marginal_proxy_baseline"] for r in rows_out]
    agg["pairwise_binary_baseline"] = {
        "accepted_pair_accuracy": _mean([float(x["accepted_pair_accuracy"]) for x in p_rows]),
        "coverage": _mean([float(x["coverage"]) for x in p_rows]),
        "defer_rate": _mean([float(x["defer_rate"]) for x in p_rows]),
    }
    agg["penalized_marginal_proxy_baseline"] = {
        "accepted_pair_accuracy": _mean([float(x["accepted_pair_accuracy"]) for x in q_rows]),
        "coverage": _mean([float(x["coverage"]) for x in q_rows]),
        "defer_rate": _mean([float(x["defer_rate"]) for x in q_rows]),
    }

    full = agg["variants"].get("full_method", {})
    agg["deltas"] = {
        "full_vs_pairwise_accuracy": float(full.get("accepted_pair_accuracy", 0.0)) - float(agg["pairwise_binary_baseline"].get("accepted_pair_accuracy", 0.0)),
        "full_vs_value_only_accuracy": float(full.get("accepted_pair_accuracy", 0.0)) - float(agg["variants"].get("value_only", {}).get("accepted_pair_accuracy", 0.0)),
    }

    reference = _load_reference_strong_baseline()
    caveats = []
    if missing_regimes:
        caveats.append("Some requested regime directories were missing under targets-root; see missing_regimes in summary.")

    config = {
        "targets_root": args.targets_root,
        "run_id": args.run_id,
        "regimes": regimes,
        "seeds": seeds,
        "feature_set": args.feature_set,
        "coverage_floor": args.coverage_floor,
        "ablation_variants": ABLATION_ORDER,
        "outside_gap_threshold": args.outside_gap_threshold,
        "oracle_defer_score_threshold": args.oracle_defer_score_threshold,
    }
    summary = {
        "config": config,
        "aggregate": agg,
        "rows": rows_out,
        "missing_regimes": missing_regimes,
        "reference_strong_tie_aware_baseline": reference,
        "assumptions": {
            "value_target": "estimated_value_if_allocate_next",
            "raw_uncertainty": "allocation_value_std",
            "learned_risk": "ridge absolute residual proxy",
            "outside_option": "pair_best_vs_outside_gap",
        },
        "caveats": caveats,
    }

    (run_dir / "strict_validation_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (run_dir / "strict_validation_results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (run_dir / "strict_validation_summary.json").write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "targets_root": args.targets_root,
                "aggregate": agg,
                "missing_regimes": missing_regimes,
                "caveats": caveats,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "strict_validation_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    "strict_validation_config.json",
                    "strict_validation_results.json",
                    "strict_validation_summary.json",
                    "strict_validation_manifest.json",
                ],
                "invocation": "python scripts/run_branch_value_uncertainty_strict_validation_pass.py --targets-root <targets_root> --run-id <run_id>",
                "notes": [
                    "Strict validation pass with ablations and baseline comparisons.",
                    "Includes budget/dataset slice summaries where data is available.",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_id": args.run_id, "aggregate": agg, "missing_regimes": missing_regimes}, indent=2))


if __name__ == "__main__":
    main()
