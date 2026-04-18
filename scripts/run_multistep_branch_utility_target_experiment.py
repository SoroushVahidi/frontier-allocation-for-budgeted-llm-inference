#!/usr/bin/env python3
"""Bounded validation pass for multistep branch-utility target horizons."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from statistics import pstdev
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


def _slice_acc(rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int], *, mask: Callable[[dict[str, Any]], bool]) -> tuple[float, int]:
    subset = [r for r in rows if mask(r)]
    if not subset:
        return 0.0, 0
    return float(sum(int(pred_fn(r) == int(r.get("label", 0))) for r in subset) / len(subset)), len(subset)


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
            "strict_slice_accepted_accuracy": 0.0,
            "strict_slice_n": 0,
        }

    near_acc, near_n = _slice_acc(test, pred_fn, mask=lambda r: bool(r.get("near_tie_flag", False)))
    adj_acc, adj_n = _slice_acc(test, pred_fn, mask=lambda r: str(r.get("pair_type", "")) == "adjacent_rank")
    strict_acc, strict_n = _slice_acc(
        test,
        pred_fn,
        mask=lambda r: bool(r.get("near_tie_flag", False)) and str(r.get("pair_type", "")) == "adjacent_rank",
    )
    overall_acc, overall_n = _slice_acc(test, pred_fn, mask=lambda _r: True)
    return {
        "accepted_accuracy": overall_acc,
        "coverage": 1.0,
        "defer_rate": 0.0,
        "accepted_n": overall_n,
        "test_n": len(test),
        "near_tie_accepted_accuracy": near_acc,
        "near_tie_n": near_n,
        "adjacent_rank_accepted_accuracy": adj_acc,
        "adjacent_rank_n": adj_n,
        "strict_slice_accepted_accuracy": strict_acc,
        "strict_slice_n": strict_n,
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


def _target_distribution_diagnostics(candidates: list[dict[str, Any]], eval_pairs: list[dict[str, Any]], target_field: str) -> dict[str, Any]:
    vals = [float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in candidates]
    one_step_vals = [float(r.get("estimated_value_if_allocate_next", 0.0)) for r in candidates]

    sid_flags: dict[str, dict[str, bool]] = {}
    for p in eval_pairs:
        if str(p.get("split")) != "test":
            continue
        sid = str(p.get("state_id", ""))
        sid_flags.setdefault(sid, {"near": False, "adj": False})
        sid_flags[sid]["near"] = bool(sid_flags[sid]["near"] or bool(p.get("near_tie_flag", False)))
        sid_flags[sid]["adj"] = bool(sid_flags[sid]["adj"] or str(p.get("pair_type", "")) == "adjacent_rank")

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
        if bool(sid_flags.get(sid, {}).get("near", False)):
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
        "one_step_stats_all": _stats(one_step_vals),
        "target_stats_near_tie_state": _stats(near_vals),
        "target_stats_non_near_tie_state": _stats(non_near_vals),
        "one_step_stats_near_tie_state": _stats(near_ones),
        "one_step_stats_non_near_tie_state": _stats(non_near_ones),
    }


def _state_best_branch_map(candidates: list[dict[str, Any]], target_field: str) -> dict[str, str]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r.get("state_id", "")), []).append(r)
    out: dict[str, str] = {}
    for sid, rows in by_state.items():
        if len(rows) < 2:
            continue
        best = max(rows, key=lambda rr: float(rr.get(target_field, rr.get("estimated_value_if_allocate_next", 0.0))))
        out[sid] = str(best.get("branch_id", ""))
    return out


def _build_state_hardness_flags(eval_pairs: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    flags: dict[str, dict[str, bool]] = {}
    for r in eval_pairs:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        f = flags.setdefault(sid, {"near_tie": False, "adjacent": False})
        f["near_tie"] = bool(f["near_tie"] or bool(r.get("near_tie_flag", False)))
        f["adjacent"] = bool(f["adjacent"] or str(r.get("pair_type", "")) == "adjacent_rank")
    return flags


def _disagreement_diagnostics(k1_best: dict[str, str], k3_best: dict[str, str], state_flags: dict[str, dict[str, bool]]) -> dict[str, Any]:
    sids = sorted(set(k1_best) & set(k3_best))

    def _rate(mask: Callable[[str], bool]) -> dict[str, Any]:
        use = [sid for sid in sids if mask(sid)]
        if not use:
            return {"states": 0, "disagreement_n": 0, "disagreement_rate": 0.0}
        dis = sum(int(k1_best[sid] != k3_best[sid]) for sid in use)
        return {"states": len(use), "disagreement_n": int(dis), "disagreement_rate": float(dis / len(use))}

    changed = [sid for sid in sids if k1_best[sid] != k3_best[sid]]
    return {
        "overall": _rate(lambda _sid: True),
        "near_tie_state": _rate(lambda sid: bool(state_flags.get(sid, {}).get("near_tie", False))),
        "non_near_tie_state": _rate(lambda sid: not bool(state_flags.get(sid, {}).get("near_tie", False))),
        "adjacent_rank_heavy_state": _rate(lambda sid: bool(state_flags.get(sid, {}).get("adjacent", False))),
        "changed_state_examples": changed[:100],
    }


def _support_diagnostics(eval_pairs: list[dict[str, Any]], eval_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    test_pairs = [r for r in eval_pairs if str(r.get("split")) == "test"]
    test_candidates = [r for r in eval_candidates if str(r.get("split")) == "test"]
    train_pairs = [r for r in eval_pairs if str(r.get("split")) == "train"]
    train_candidates = [r for r in eval_candidates if str(r.get("split")) == "train"]

    test_state_ids = sorted({str(r.get("state_id", "")) for r in test_pairs})
    near_tie_pairs = [r for r in test_pairs if bool(r.get("near_tie_flag", False))]
    adjacent_pairs = [r for r in test_pairs if str(r.get("pair_type", "")) == "adjacent_rank"]
    strict_pairs = [r for r in test_pairs if bool(r.get("near_tie_flag", False)) and str(r.get("pair_type", "")) == "adjacent_rank"]

    near_state_ids = sorted({str(r.get("state_id", "")) for r in near_tie_pairs})
    adjacent_state_ids = sorted({str(r.get("state_id", "")) for r in adjacent_pairs})
    pair_rows = len(test_pairs) + len(train_pairs)

    warnings = []
    if len(test_pairs) < 30:
        warnings.append("Very small test pair denominator (<30); accuracy deltas are fragile.")
    if len(near_tie_pairs) < 10:
        warnings.append("Near-tie test support is very small (<10 pairs).")
    if len(strict_pairs) < 8:
        warnings.append("Strict matched canonical slice support is very small (<8 pairs).")

    return {
        "state_counts": {
            "test_states": len(test_state_ids),
            "near_tie_test_states": len(near_state_ids),
            "adjacent_rank_test_states": len(adjacent_state_ids),
        },
        "candidate_row_counts": {
            "train": len(train_candidates),
            "test": len(test_candidates),
            "total": len(train_candidates) + len(test_candidates),
        },
        "pair_row_counts": {
            "train": len(train_pairs),
            "test": len(test_pairs),
            "total": pair_rows,
            "near_tie_test_pairs": len(near_tie_pairs),
            "adjacent_rank_test_pairs": len(adjacent_pairs),
            "strict_slice_test_pairs": len(strict_pairs),
        },
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded multi-step branch utility target validation")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--k1-regime", default="multistep_branch_utility_target_k1")
    p.add_argument("--k2-regime", default="multistep_branch_utility_target_k2")
    p.add_argument("--k3-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--multistep-target-field", default="multistep_branch_utility_target")
    p.add_argument("--strict-slice-name", default="near_tie_and_adjacent_rank")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_csv(args.seeds)
    targets_root = Path(args.targets_root)

    regime_to_mode = {
        str(args.baseline_regime): "baseline_current_matched",
        str(args.k1_regime): "multistep_k1",
        str(args.k2_regime): "multistep_k2",
        str(args.k3_regime): "multistep_k3",
    }

    per_seed_rows: list[dict[str, Any]] = []
    target_diag_rows: list[dict[str, Any]] = []
    per_seed_disagreement_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

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
        eval_candidates = baseline_tables["candidates"]
        support_rows.append({"seed": int(seed), **_support_diagnostics(eval_pair_rows, eval_candidates)})

        kbest: dict[str, dict[str, str]] = {}
        state_flags = _build_state_hardness_flags(eval_pair_rows)

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
                pointwise_target_field=(str(args.multistep_target_field) if mode != "baseline_current_matched" else "estimated_value_if_allocate_next"),
            )
            tables = prepare_learning_tables(raw, cfg)
            candidates = tables["candidates"]

            if mode == "baseline_current_matched":
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
                kbest[mode] = _state_best_branch_map(candidates, target_field=target_field)

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

        if "multistep_k1" in kbest and "multistep_k3" in kbest:
            per_seed_disagreement_rows.append(
                {
                    "seed": int(seed),
                    "comparison": "k1_vs_k3",
                    **_disagreement_diagnostics(kbest["multistep_k1"], kbest["multistep_k3"], state_flags),
                }
            )

    modes = ["baseline_current_matched", "multistep_k1", "multistep_k2", "multistep_k3"]
    aggregate: dict[str, Any] = {}
    for mode in modes:
        rows = [r for r in per_seed_rows if r["mode"] == mode]
        aggregate[mode] = {
            "seeds": len(rows),
            "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
            "accepted_accuracy_std": float(pstdev([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows])) if len(rows) > 1 else 0.0,
            "coverage_mean": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
            "defer_rate_mean": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
            "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
            "strict_slice_accepted_accuracy_mean": _mean([float(r["metrics"].get("strict_slice_accepted_accuracy", 0.0)) for r in rows]),
        }

    baseline = aggregate.get("baseline_current_matched", {})
    comparison: dict[str, Any] = {}
    for mode in ["multistep_k1", "multistep_k2", "multistep_k3"]:
        vals = aggregate.get(mode, {})
        comparison[mode] = {
            "delta_accepted_accuracy_vs_baseline": float(vals.get("accepted_accuracy_mean", 0.0) - baseline.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_baseline": float(vals.get("near_tie_accepted_accuracy_mean", 0.0) - baseline.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_adjacent_rank_accepted_accuracy_vs_baseline": float(vals.get("adjacent_rank_accepted_accuracy_mean", 0.0) - baseline.get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "delta_strict_slice_accepted_accuracy_vs_baseline": float(vals.get("strict_slice_accepted_accuracy_mean", 0.0) - baseline.get("strict_slice_accepted_accuracy_mean", 0.0)),
            "delta_coverage_vs_baseline": float(vals.get("coverage_mean", 0.0) - baseline.get("coverage_mean", 0.0)),
        }

    trend = {
        "accepted_accuracy": {
            "k1": float(aggregate.get("multistep_k1", {}).get("accepted_accuracy_mean", 0.0)),
            "k2": float(aggregate.get("multistep_k2", {}).get("accepted_accuracy_mean", 0.0)),
            "k3": float(aggregate.get("multistep_k3", {}).get("accepted_accuracy_mean", 0.0)),
            "k1_to_k2_delta": float(aggregate.get("multistep_k2", {}).get("accepted_accuracy_mean", 0.0) - aggregate.get("multistep_k1", {}).get("accepted_accuracy_mean", 0.0)),
            "k2_to_k3_delta": float(aggregate.get("multistep_k3", {}).get("accepted_accuracy_mean", 0.0) - aggregate.get("multistep_k2", {}).get("accepted_accuracy_mean", 0.0)),
        },
        "near_tie_accepted_accuracy": {
            "k1": float(aggregate.get("multistep_k1", {}).get("near_tie_accepted_accuracy_mean", 0.0)),
            "k2": float(aggregate.get("multistep_k2", {}).get("near_tie_accepted_accuracy_mean", 0.0)),
            "k3": float(aggregate.get("multistep_k3", {}).get("near_tie_accepted_accuracy_mean", 0.0)),
        },
        "adjacent_rank_accepted_accuracy": {
            "k1": float(aggregate.get("multistep_k1", {}).get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "k2": float(aggregate.get("multistep_k2", {}).get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "k3": float(aggregate.get("multistep_k3", {}).get("adjacent_rank_accepted_accuracy_mean", 0.0)),
        },
    }

    strict_summary = {
        "strict_slice_name": str(args.strict_slice_name),
        "description": "Matched canonical strict slice requiring both near_tie_flag and adjacent_rank pair type.",
        "aggregate_by_mode": {m: {"strict_slice_accepted_accuracy_mean": aggregate.get(m, {}).get("strict_slice_accepted_accuracy_mean", 0.0)} for m in modes},
        "delta_vs_baseline": {m: comparison.get(m, {}).get("delta_strict_slice_accepted_accuracy_vs_baseline", 0.0) for m in ["multistep_k1", "multistep_k2", "multistep_k3"]},
    }

    _write_json(out_dir / "config_manifest.json", {
        "run_id": str(args.run_id),
        "targets_root": str(targets_root),
        "seeds": seeds,
        "feature_set": str(args.feature_set),
        "near_tie_margin": float(args.near_tie_margin),
        "regime_to_mode": regime_to_mode,
        "multistep_target_field": str(args.multistep_target_field),
        "strict_slice_name": str(args.strict_slice_name),
        "command": " ".join(sys.argv),
    })
    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed_rows})
    _write_json(out_dir / "target_diagnostics_summary.json", {"rows": target_diag_rows})
    _write_json(out_dir / "disagreement_diagnostics.json", {"rows": per_seed_disagreement_rows})
    _write_json(out_dir / "support_diagnostics.json", {"rows": support_rows})
    _write_json(out_dir / "matched_summary_by_horizon.json", {"aggregate": aggregate, "comparison_vs_baseline": comparison, "horizon_trend": trend})
    _write_json(out_dir / "aggregate_comparison_summary.json", {"aggregate": aggregate, "comparison_vs_baseline": comparison, "horizon_trend": trend})
    _write_json(out_dir / "stricter_validation_summary.json", strict_summary)

    print(json.dumps({"output_dir": str(out_dir), "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
