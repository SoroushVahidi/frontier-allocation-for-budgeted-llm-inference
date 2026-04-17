#!/usr/bin/env python3
"""Bounded probabilistic branch-allocation experiment on canonical branch-value path.

Modes:
- baseline_canonical: existing branch-value + uncertainty compare/defer behavior.
- deterministic_value_top1: forced top-1 by predicted branch value (no defer).
- probabilistic_value_choice: forced stochastic commit via softmax(value/temperature).
- probabilistic_value_choice_temperature_sweep: tiny bounded temperature sweep.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, load_label_artifacts, prepare_learning_tables


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded probabilistic branch-value branch-allocation experiment")
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
    p.add_argument("--temperature", type=float, default=0.75)
    p.add_argument("--temperature-grid", default="0.50,0.75,1.00")
    p.add_argument("--probability-epsilon", type=float, default=1e-6)
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


def _canonical_defer(row: dict[str, Any], *, gap_threshold: float, z_threshold: float, outside_gap_threshold: float) -> tuple[bool, float]:
    diff = float(row.get("pred_value_i", 0.0)) - float(row.get("pred_value_j", 0.0))
    abs_gap = abs(diff)
    raw_si = float(row.get("raw_sigma_i", 0.0))
    raw_sj = float(row.get("raw_sigma_j", 0.0))
    lr_si = float(row.get("learned_sigma_i", 0.0))
    lr_sj = float(row.get("learned_sigma_j", 0.0))
    pair_sigma = float(np.sqrt((0.5 * raw_si + 0.5 * lr_si) ** 2 + (0.5 * raw_sj + 0.5 * lr_sj) ** 2))
    z_gap = abs_gap / max(1e-6, pair_sigma)
    outside_gap = float(row.get("pair_best_vs_outside_gap", 0.0))
    defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
    if outside_gap <= outside_gap_threshold and z_gap <= z_threshold:
        defer = True
    return bool(defer), float(z_gap)


def _stable_softmax_prob_i(vi: float, vj: float, *, temperature: float, eps: float) -> float:
    t = max(1e-6, float(temperature))
    z0 = vi / t
    z1 = vj / t
    zmax = max(z0, z1)
    e0 = math.exp(z0 - zmax)
    e1 = math.exp(z1 - zmax)
    p_i = e0 / max(1e-12, e0 + e1)
    p_i = min(1.0 - eps, max(eps, p_i))
    return float(p_i)


def _entropy_bernoulli(p: float) -> float:
    pp = min(1.0 - 1e-12, max(1e-12, p))
    return float(-pp * math.log(pp) - (1.0 - pp) * math.log(1.0 - pp))


def _evaluate_mode(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    split: str,
    seed: int,
    gap_threshold: float,
    z_threshold: float,
    outside_gap_threshold: float,
    temperature: float,
    eps: float,
) -> dict[str, Any]:
    subset = [r for r in rows if str(r.get("split")) == split]
    accepted: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    entropy_vals: list[float] = []

    for idx, r in enumerate(subset):
        vi = float(r.get("pred_value_i", 0.0))
        vj = float(r.get("pred_value_j", 0.0))
        diff = vi - vj

        if mode == "baseline_canonical":
            defer, _ = _canonical_defer(
                r,
                gap_threshold=float(gap_threshold),
                z_threshold=float(z_threshold),
                outside_gap_threshold=float(outside_gap_threshold),
            )
            if defer:
                r["_action"] = None
                r["_selection_prob_i"] = None
                deferred.append(r)
                continue
            action = 1 if diff >= 0.0 else 0
            r["_action"] = int(action)
            r["_selection_prob_i"] = 1.0 if action == 1 else 0.0
            accepted.append(r)
        elif mode == "deterministic_value_top1":
            action = 1 if diff >= 0.0 else 0
            r["_action"] = int(action)
            r["_selection_prob_i"] = 1.0 if action == 1 else 0.0
            accepted.append(r)
        elif mode == "probabilistic_value_choice":
            p_i = _stable_softmax_prob_i(vi, vj, temperature=temperature, eps=eps)
            # deterministic pseudo-random stream for exact reproducibility
            rng = np.random.default_rng(seed * 1000003 + idx)
            action = 1 if float(rng.uniform()) < p_i else 0
            r["_action"] = int(action)
            r["_selection_prob_i"] = float(p_i)
            entropy_vals.append(_entropy_bernoulli(p_i))
            accepted.append(r)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _acc(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        return sum(int(int(rr["_action"]) == int(rr.get("label", 0))) for rr in items) / len(items)

    near = [r for r in accepted if bool(r.get("near_tie_flag", False))]
    adj = [r for r in accepted if str(r.get("pair_type", "")) == "adjacent_rank"]

    return {
        "accepted_pair_accuracy": _acc(accepted),
        "coverage": len(accepted) / max(1, len(subset)),
        "defer_rate": len(deferred) / max(1, len(subset)),
        "near_tie_accepted_pair_accuracy": _acc(near),
        "adjacent_rank_accepted_pair_accuracy": _acc(adj),
        "accepted_mean_true_value_gap": _mean([float(r.get("pair_value_gap", 0.0)) for r in accepted]),
        "deferred_mean_true_value_gap": _mean([float(r.get("pair_value_gap", 0.0)) for r in deferred]),
        "accepted_mean_pair_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in accepted]),
        "deferred_mean_pair_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in deferred]),
        "mean_selection_entropy_nats": _mean(entropy_vals),
        "test_pairs": float(len(subset)),
    }


def main() -> None:
    args = parse_args()
    run_dir = Path(args.output_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    regimes = [x.strip() for x in str(args.regimes).split(",") if x.strip()]
    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    gap_grid = _parse_csv_floats(args.threshold_grid_gap)
    z_grid = _parse_csv_floats(args.threshold_grid_z)
    temp_grid = _parse_csv_floats(args.temperature_grid)

    per_seed_rows: list[dict[str, Any]] = []

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            raise FileNotFoundError(f"Missing regime directory: {regime_dir}")

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
            pair_rows = tables["pairwise"]
            candidates = tables["candidates"]

            cand_lookup = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
            value_model = _fit_value(candidates)
            risk_model = _fit_risk(candidates, value_model)

            for r in pair_rows:
                ci = cand_lookup[(str(r["state_id"]), str(r["branch_i"]))]
                cj = cand_lookup[(str(r["state_id"]), str(r["branch_j"]))]
                r["pred_value_i"] = _pred_value(value_model, ci)
                r["pred_value_j"] = _pred_value(value_model, cj)
                r["raw_sigma_i"] = max(1e-6, float(ci.get("allocation_value_std", 0.0)))
                r["raw_sigma_j"] = max(1e-6, float(cj.get("allocation_value_std", 0.0)))
                r["learned_sigma_i"] = _pred_learned_sigma(risk_model, ci)
                r["learned_sigma_j"] = _pred_learned_sigma(risk_model, cj)

            best = None
            for g in gap_grid:
                for z in z_grid:
                    m_val = _evaluate_mode(
                        pair_rows,
                        mode="baseline_canonical",
                        split="val",
                        seed=seed,
                        gap_threshold=g,
                        z_threshold=z,
                        outside_gap_threshold=float(args.outside_gap_threshold),
                        temperature=float(args.temperature),
                        eps=float(args.probability_epsilon),
                    )
                    if float(m_val["coverage"]) < float(args.coverage_floor):
                        continue
                    candidate = {"gap_threshold": g, "z_threshold": z, "score": float(m_val["accepted_pair_accuracy"])}
                    if best is None or candidate["score"] > best["score"]:
                        best = candidate
            if best is None:
                best = {"gap_threshold": 0.0, "z_threshold": 0.0}

            baseline_test = _evaluate_mode(
                pair_rows,
                mode="baseline_canonical",
                split="test",
                seed=seed,
                gap_threshold=float(best["gap_threshold"]),
                z_threshold=float(best["z_threshold"]),
                outside_gap_threshold=float(args.outside_gap_threshold),
                temperature=float(args.temperature),
                eps=float(args.probability_epsilon),
            )
            top1_test = _evaluate_mode(
                pair_rows,
                mode="deterministic_value_top1",
                split="test",
                seed=seed,
                gap_threshold=float(best["gap_threshold"]),
                z_threshold=float(best["z_threshold"]),
                outside_gap_threshold=float(args.outside_gap_threshold),
                temperature=float(args.temperature),
                eps=float(args.probability_epsilon),
            )
            prob_test = _evaluate_mode(
                pair_rows,
                mode="probabilistic_value_choice",
                split="test",
                seed=seed,
                gap_threshold=float(best["gap_threshold"]),
                z_threshold=float(best["z_threshold"]),
                outside_gap_threshold=float(args.outside_gap_threshold),
                temperature=float(args.temperature),
                eps=float(args.probability_epsilon),
            )

            temp_sweep = []
            for t in temp_grid:
                t_metrics = _evaluate_mode(
                    pair_rows,
                    mode="probabilistic_value_choice",
                    split="test",
                    seed=seed,
                    gap_threshold=float(best["gap_threshold"]),
                    z_threshold=float(best["z_threshold"]),
                    outside_gap_threshold=float(args.outside_gap_threshold),
                    temperature=float(t),
                    eps=float(args.probability_epsilon),
                )
                temp_sweep.append({"temperature": float(t), "metrics": t_metrics})

            per_seed_rows.append(
                {
                    "regime": regime,
                    "seed": seed,
                    "selected_thresholds_from_canonical": {"gap_threshold": float(best["gap_threshold"]), "z_threshold": float(best["z_threshold"])} ,
                    "mode_metrics": {
                        "baseline_canonical": baseline_test,
                        "deterministic_value_top1": top1_test,
                        "probabilistic_value_choice": prob_test,
                    },
                    "probabilistic_temperature_sweep": temp_sweep,
                    "risk_head_status": str(risk_model.get("status", "unknown")),
                }
            )

    modes = ["baseline_canonical", "deterministic_value_top1", "probabilistic_value_choice"]
    aggregate_by_mode: dict[str, Any] = {}
    for mode in modes:
        mode_rows = [r["mode_metrics"][mode] for r in per_seed_rows]
        aggregate_by_mode[mode] = {
            "accepted_pair_accuracy": _mean([float(m["accepted_pair_accuracy"]) for m in mode_rows]),
            "coverage": _mean([float(m["coverage"]) for m in mode_rows]),
            "defer_rate": _mean([float(m["defer_rate"]) for m in mode_rows]),
            "near_tie_accepted_pair_accuracy": _mean([float(m["near_tie_accepted_pair_accuracy"]) for m in mode_rows]),
            "adjacent_rank_accepted_pair_accuracy": _mean([float(m["adjacent_rank_accepted_pair_accuracy"]) for m in mode_rows]),
            "mean_selection_entropy_nats": _mean([float(m["mean_selection_entropy_nats"]) for m in mode_rows]),
            "test_pairs": _mean([float(m["test_pairs"]) for m in mode_rows]),
        }

    def _delta(mode: str, ref: str, key: str) -> float:
        return float(aggregate_by_mode[mode][key]) - float(aggregate_by_mode[ref][key])

    aggregate_comparison = {
        "probabilistic_vs_baseline": {
            "delta_accepted_pair_accuracy": _delta("probabilistic_value_choice", "baseline_canonical", "accepted_pair_accuracy"),
            "delta_coverage": _delta("probabilistic_value_choice", "baseline_canonical", "coverage"),
            "delta_defer_rate": _delta("probabilistic_value_choice", "baseline_canonical", "defer_rate"),
            "delta_near_tie_accepted_pair_accuracy": _delta("probabilistic_value_choice", "baseline_canonical", "near_tie_accepted_pair_accuracy"),
            "delta_adjacent_rank_accepted_pair_accuracy": _delta("probabilistic_value_choice", "baseline_canonical", "adjacent_rank_accepted_pair_accuracy"),
        },
        "probabilistic_vs_deterministic_top1": {
            "delta_accepted_pair_accuracy": _delta("probabilistic_value_choice", "deterministic_value_top1", "accepted_pair_accuracy"),
            "delta_near_tie_accepted_pair_accuracy": _delta("probabilistic_value_choice", "deterministic_value_top1", "near_tie_accepted_pair_accuracy"),
            "delta_adjacent_rank_accepted_pair_accuracy": _delta("probabilistic_value_choice", "deterministic_value_top1", "adjacent_rank_accepted_pair_accuracy"),
            "delta_mean_selection_entropy_nats": _delta("probabilistic_value_choice", "deterministic_value_top1", "mean_selection_entropy_nats"),
        },
    }

    sweep_summary: list[dict[str, Any]] = []
    for t in temp_grid:
        t_rows = []
        for row in per_seed_rows:
            for s in row["probabilistic_temperature_sweep"]:
                if float(s["temperature"]) == float(t):
                    t_rows.append(s["metrics"])
                    break
        sweep_summary.append(
            {
                "temperature": float(t),
                "accepted_pair_accuracy": _mean([float(m["accepted_pair_accuracy"]) for m in t_rows]),
                "coverage": _mean([float(m["coverage"]) for m in t_rows]),
                "defer_rate": _mean([float(m["defer_rate"]) for m in t_rows]),
                "near_tie_accepted_pair_accuracy": _mean([float(m["near_tie_accepted_pair_accuracy"]) for m in t_rows]),
                "adjacent_rank_accepted_pair_accuracy": _mean([float(m["adjacent_rank_accepted_pair_accuracy"]) for m in t_rows]),
                "mean_selection_entropy_nats": _mean([float(m["mean_selection_entropy_nats"]) for m in t_rows]),
            }
        )

    config = {
        "targets_root": args.targets_root,
        "run_id": args.run_id,
        "regimes": regimes,
        "seeds": seeds,
        "feature_set": args.feature_set,
        "coverage_floor": args.coverage_floor,
        "threshold_grid_gap": gap_grid,
        "threshold_grid_z": z_grid,
        "outside_gap_threshold": args.outside_gap_threshold,
        "temperature": args.temperature,
        "temperature_grid": temp_grid,
        "probability_epsilon": args.probability_epsilon,
        "probability_rule": "p(i|v_i,v_j,T)=clip( exp(v_i/T)/(exp(v_i/T)+exp(v_j/T)), eps, 1-eps )",
        "randomness": "deterministic pseudo-random stream per seed and row index",
    }

    manifest = {
        "artifacts": [
            "probabilistic_branch_allocation_config.json",
            "probabilistic_branch_allocation_per_seed_summary.json",
            "probabilistic_branch_allocation_matched_summary_by_mode.json",
            "probabilistic_branch_allocation_aggregate_comparison.json",
            "probabilistic_branch_allocation_temperature_sweep_summary.json",
            "probabilistic_branch_allocation_manifest.json",
            "probabilistic_branch_allocation_commands_and_caveats.md",
        ],
        "modes": modes + ["probabilistic_value_choice_temperature_sweep"],
    }

    (run_dir / "probabilistic_branch_allocation_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (run_dir / "probabilistic_branch_allocation_per_seed_summary.json").write_text(json.dumps(per_seed_rows, indent=2) + "\n", encoding="utf-8")
    (run_dir / "probabilistic_branch_allocation_matched_summary_by_mode.json").write_text(json.dumps(aggregate_by_mode, indent=2) + "\n", encoding="utf-8")
    (run_dir / "probabilistic_branch_allocation_aggregate_comparison.json").write_text(json.dumps(aggregate_comparison, indent=2) + "\n", encoding="utf-8")
    (run_dir / "probabilistic_branch_allocation_temperature_sweep_summary.json").write_text(json.dumps(sweep_summary, indent=2) + "\n", encoding="utf-8")
    (run_dir / "probabilistic_branch_allocation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": args.run_id, "aggregate_by_mode": aggregate_by_mode, "aggregate_comparison": aggregate_comparison}, indent=2))


if __name__ == "__main__":
    main()
