#!/usr/bin/env python3
"""Bounded experiment: multi-step branch-utility target vs canonical one-step baseline."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
import sys

import numpy as np
from sklearn.linear_model import Ridge

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


def _pair_pred_from_score(score_fn: Callable[[dict[str, Any]], float], row: dict[str, Any]) -> int:
    si = float(score_fn({"x": row["x_i"]}))
    sj = float(score_fn({"x": row["x_j"]}))
    return 1 if si >= sj else 0


def _pair_metrics(pair_rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int]) -> dict[str, Any]:
    test = [r for r in pair_rows if str(r.get("split")) == "test"]
    if not test:
        return {
            "accepted_accuracy": 0.0,
            "coverage": 0.0,
            "defer_rate": 0.0,
            "accepted_n": 0,
            "test_n": 0,
            "near_tie_accepted_accuracy": 0.0,
            "near_tie_n": 0,
            "adjacent_rank_accepted_accuracy": 0.0,
            "adjacent_rank_n": 0,
        }

    def _acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return float(sum(int(pred_fn(r) == int(r.get("label", 0))) for r in rows) / len(rows))

    near = [r for r in test if bool(r.get("near_tie_flag", False))]
    adj = [r for r in test if str(r.get("pair_type", "")) == "adjacent_rank"]
    return {
        "accepted_accuracy": _acc(test),
        "coverage": 1.0,
        "defer_rate": 0.0,
        "accepted_n": len(test),
        "test_n": len(test),
        "near_tie_accepted_accuracy": _acc(near),
        "near_tie_n": len(near),
        "adjacent_rank_accepted_accuracy": _acc(adj),
        "adjacent_rank_n": len(adj),
    }


def _fit_pointwise_target(candidates: list[dict[str, Any]], target_field: str, seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in train], dtype=float)
    if np.std(y) <= 1e-12:
        return {"status": "degenerate_target", "training_rows": len(train), "target_field": target_field}
    m = Ridge(alpha=1.0, random_state=seed)
    m.fit(x, y)
    return {
        "status": "ok",
        "target_field": target_field,
        "weights": [float(v) for v in m.coef_],
        "intercept": float(m.intercept_),
        "training_rows": len(train),
    }


def _scorer_from_linear(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    w = np.array(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    return lambda row: float(np.dot(w, np.array(row["x"], dtype=float)) + b)


def _target_distribution_diagnostics(candidates: list[dict[str, Any]], pair_rows: list[dict[str, Any]], target_field: str) -> dict[str, Any]:
    vals = [float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in candidates]
    ones = [float(r.get("estimated_value_if_allocate_next", 0.0)) for r in candidates]

    sid_to_near: dict[str, bool] = {}
    for p in pair_rows:
        if str(p.get("split")) != "test":
            continue
        sid = str(p.get("state_id", ""))
        flag = bool(p.get("near_tie_flag", False)) or str(p.get("pair_type", "")) == "adjacent_rank"
        sid_to_near[sid] = bool(sid_to_near.get(sid, False) or flag)

    near_vals: list[float] = []
    non_near_vals: list[float] = []
    near_ones: list[float] = []
    non_near_ones: list[float] = []
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        tv = float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0)))
        ov = float(r.get("estimated_value_if_allocate_next", 0.0))
        if bool(sid_to_near.get(sid, False)):
            near_vals.append(tv)
            near_ones.append(ov)
        else:
            non_near_vals.append(tv)
            non_near_ones.append(ov)

    def _stats(xs: list[float]) -> dict[str, float]:
        if not xs:
            return {"mean": 0.0, "std": 0.0, "p10": 0.0, "p50": 0.0, "p90": 0.0, "n": 0.0}
        arr = np.array(xs, dtype=float)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p10": float(np.percentile(arr, 10)),
            "p50": float(np.percentile(arr, 50)),
            "p90": float(np.percentile(arr, 90)),
            "n": float(len(xs)),
        }

    return {
        "target_field": target_field,
        "target_stats_all": _stats(vals),
        "one_step_stats_all": _stats(ones),
        "target_stats_near_tie_state": _stats(near_vals),
        "target_stats_non_near_tie_state": _stats(non_near_vals),
        "one_step_stats_near_tie_state": _stats(near_ones),
        "one_step_stats_non_near_tie_state": _stats(non_near_ones),
    }


def _statewise_disagreement(candidates: list[dict[str, Any]], target_field: str) -> dict[str, Any]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r.get("state_id", "")), []).append(r)

    total = 0
    disagree = 0
    details: list[dict[str, Any]] = []
    for sid, rows in by_state.items():
        if len(rows) < 2:
            continue
        total += 1
        one = str(max(rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0))).get("branch_id", ""))
        mul = str(max(rows, key=lambda r: float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0)))).get("branch_id", ""))
        is_dis = int(one != mul)
        disagree += is_dis
        if is_dis:
            details.append(
                {
                    "state_id": sid,
                    "one_step_best_branch": one,
                    "multistep_best_branch": mul,
                }
            )
    return {
        "target_field": target_field,
        "test_state_n": int(total),
        "disagreement_n": int(disagree),
        "disagreement_rate": float(disagree / max(1, total)),
        "examples": details[:100],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded multi-step branch utility target experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--k1-regime", default="multistep_branch_utility_target_k1")
    p.add_argument("--multistep-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--multistep-target-field", default="multistep_branch_utility_target")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_csv(args.seeds)
    targets_root = Path(args.targets_root)

    regime_to_mode = {
        str(args.baseline_regime): "canonical_pairwise_baseline",
        str(args.k1_regime): "multistep_branch_utility_target_k1",
        str(args.multistep_regime): "multistep_branch_utility_target_k3",
    }

    per_seed_rows: list[dict[str, Any]] = []
    target_diag_rows: list[dict[str, Any]] = []
    disagreement_rows: list[dict[str, Any]] = []

    for seed in seeds:
        baseline_regime_dir = targets_root / f"regime_{args.baseline_regime}"
        baseline_raw = load_label_artifacts(baseline_regime_dir)
        baseline_cfg = LearningConfig(
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
        baseline_tables = prepare_learning_tables(baseline_raw, baseline_cfg)
        eval_pair_rows = baseline_tables["pairwise"]

        for regime, mode in regime_to_mode.items():
            regime_dir = targets_root / f"regime_{regime}"
            raw = load_label_artifacts(regime_dir)
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
                pointwise_target_field=(str(args.multistep_target_field) if mode != "canonical_pairwise_baseline" else "estimated_value_if_allocate_next"),
            )
            tables = prepare_learning_tables(raw, cfg)
            candidates = tables["candidates"]

            if mode == "canonical_pairwise_baseline":
                models = train_models(tables, cfg)
                pmodel = models.get("pairwise", {})
                if str(pmodel.get("status")) == "ok":
                    score_fn = scorer_from_model(pmodel)
                    pred = lambda r: _pair_pred_from_score(score_fn, r)
                else:
                    const_label = int(pmodel.get("constant_label", 0))
                    pred = lambda _r: const_label
                model_status = str(pmodel.get("status", "unknown"))
            else:
                target_field = str(args.multistep_target_field)
                fitted = _fit_pointwise_target(candidates, target_field=target_field, seed=int(seed))
                if str(fitted.get("status")) == "ok":
                    score_fn = _scorer_from_linear(fitted)
                    pred = lambda r: _pair_pred_from_score(score_fn, r)
                else:
                    pred = lambda r: 1 if float(r.get("pair_value_i", 0.0)) >= float(r.get("pair_value_j", 0.0)) else 0
                model_status = str(fitted.get("status", "unknown"))
                target_diag_rows.append(
                    {
                        "seed": int(seed),
                        "mode": mode,
                        "regime": regime,
                        **_target_distribution_diagnostics(candidates, eval_pair_rows, target_field=target_field),
                    }
                )
                disagreement_rows.append(
                    {
                        "seed": int(seed),
                        "mode": mode,
                        "regime": regime,
                        **_statewise_disagreement(candidates, target_field=target_field),
                    }
                )

            metrics = _pair_metrics(eval_pair_rows, pred)
            per_seed_rows.append(
                {
                    "seed": int(seed),
                    "mode": mode,
                    "regime": regime,
                    "metrics": metrics,
                    "model_status": model_status,
                    "config": asdict(cfg),
                }
            )

    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed_rows})
    _write_json(out_dir / "target_diagnostics_summary.json", {"rows": target_diag_rows})
    _write_json(out_dir / "one_step_vs_multistep_disagreement_summary.json", {"rows": disagreement_rows})

    modes = sorted({r["mode"] for r in per_seed_rows})
    aggregate: dict[str, Any] = {}
    for mode in modes:
        rows = [r for r in per_seed_rows if r["mode"] == mode]
        aggregate[mode] = {
            "seeds": len(rows),
            "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
            "coverage_mean": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
            "defer_rate_mean": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
            "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
        }

    baseline = aggregate.get("canonical_pairwise_baseline", {})
    comparison: dict[str, Any] = {}
    for mode, vals in aggregate.items():
        if mode == "canonical_pairwise_baseline":
            continue
        comparison[mode] = {
            "delta_accepted_accuracy_vs_baseline": float(vals.get("accepted_accuracy_mean", 0.0) - baseline.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_baseline": float(vals.get("near_tie_accepted_accuracy_mean", 0.0) - baseline.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_adjacent_rank_accepted_accuracy_vs_baseline": float(vals.get("adjacent_rank_accepted_accuracy_mean", 0.0) - baseline.get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "delta_coverage_vs_baseline": float(vals.get("coverage_mean", 0.0) - baseline.get("coverage_mean", 0.0)),
        }

    ablation = {
        "k1_vs_k3": {
            "accepted_accuracy_delta": float(aggregate.get("multistep_branch_utility_target_k3", {}).get("accepted_accuracy_mean", 0.0) - aggregate.get("multistep_branch_utility_target_k1", {}).get("accepted_accuracy_mean", 0.0)),
            "near_tie_accuracy_delta": float(aggregate.get("multistep_branch_utility_target_k3", {}).get("near_tie_accepted_accuracy_mean", 0.0) - aggregate.get("multistep_branch_utility_target_k1", {}).get("near_tie_accepted_accuracy_mean", 0.0)),
            "adjacent_accuracy_delta": float(aggregate.get("multistep_branch_utility_target_k3", {}).get("adjacent_rank_accepted_accuracy_mean", 0.0) - aggregate.get("multistep_branch_utility_target_k1", {}).get("adjacent_rank_accepted_accuracy_mean", 0.0)),
        }
    }

    _write_json(out_dir / "matched_summary_by_mode_regime.json", {"aggregate": aggregate, "comparison_vs_baseline": comparison})
    _write_json(out_dir / "aggregate_comparison_summary.json", {"aggregate": aggregate, "comparison_vs_baseline": comparison})
    _write_json(out_dir / "ablation_summary.json", ablation)
    _write_json(
        out_dir / "config_manifest.json",
        {
            "run_id": str(args.run_id),
            "targets_root": str(targets_root),
            "seeds": seeds,
            "feature_set": str(args.feature_set),
            "near_tie_margin": float(args.near_tie_margin),
            "regime_to_mode": regime_to_mode,
            "multistep_target_field": str(args.multistep_target_field),
        },
    )

    print(json.dumps({"output_dir": str(out_dir), "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
