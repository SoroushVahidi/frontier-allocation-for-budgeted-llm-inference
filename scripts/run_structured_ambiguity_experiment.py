#!/usr/bin/env python3
"""Bounded structured-ambiguity experiment for branch allocation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run structured ambiguity matched experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="")
    p.add_argument("--seeds", default="17,29,43")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--accepted-accuracy-min-coverage", type=float, default=0.6)
    p.add_argument("--coverage-min-accepted-accuracy", type=float, default=0.75)
    p.add_argument("--include-calibrated", action="store_true")
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    return sum(vals) / max(1, len(vals))


def _extract_pairwise(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "three_way_accuracy_test": None,
        "accepted_only_accuracy_test": None,
        "coverage_test": None,
        "defer_f1_test": None,
        "near_tie_accepted_accuracy_test": None,
        "adjacent_rank_accepted_accuracy_test": None,
        "exact_promoted_hard_region_accepted_accuracy_test": None,
        "pairwise_accuracy_test": float(m.get("pairwise_accuracy_test", 0.0)),
        "near_tie_pairwise_accuracy_test": float(m.get("near_tie_pairwise_accuracy_test", 0.0)),
        "adjacent_rank_pairwise_accuracy_test": float(m.get("adjacent_rank_pairwise_accuracy_test", 0.0)),
        "exact_promoted_hard_region_pairwise_accuracy_test": float(m.get("exact_promoted_hard_region_pairwise_accuracy_test", 0.0)),
    }


def _extract_defer(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "three_way_accuracy_test": float(m.get("three_way_accuracy_test", 0.0)),
        "accepted_only_accuracy_test": float(m.get("accepted_only_accuracy_test", 0.0)),
        "coverage_test": float(m.get("coverage_test", 0.0)),
        "defer_f1_test": float(m.get("defer_f1_test", 0.0)),
        "near_tie_accepted_accuracy_test": float(m.get("near_tie_accepted_accuracy_test", 0.0)),
        "adjacent_rank_accepted_accuracy_test": float(m.get("adjacent_rank_accepted_accuracy_test", 0.0)),
        "exact_promoted_hard_region_accepted_accuracy_test": float(m.get("exact_promoted_hard_region_accepted_accuracy_test", 0.0)),
        "best_accepted_accuracy_under_min_coverage_test": float(m.get("best_accepted_accuracy_under_min_coverage_test", {}).get("accepted_only_accuracy", 0.0)),
        "best_coverage_under_min_accepted_accuracy_test": float(m.get("best_coverage_under_min_accepted_accuracy_test", {}).get("coverage", 0.0)),
    }


def _run_setting(artifacts: dict[str, list[dict[str, Any]]], out_dir: Path, regime: str, seed: int, cfg: LearningConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    tables = prepare_learning_tables(artifacts, cfg)
    models = train_models(tables, cfg, model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / cfg.defer_target_mode)
    evals = evaluate_models(models, tables, cfg)
    defer_metrics = evals.get("pairwise_defer_classifier", {})
    return evals, {
        "threshold_trace_test": defer_metrics.get("threshold_trace_test", []),
        "decision_buckets_test": defer_metrics.get("decision_buckets_test", {}),
        "calibration_used": defer_metrics.get("calibration_used", {}),
    }


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or f"structured_ambiguity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [s.strip() for s in str(args.regimes).split(",") if s.strip()]

    rows: list[dict[str, Any]] = []
    traces: dict[str, Any] = {}
    nested: dict[str, Any] = {"run_id": run_id, "regimes": regimes, "seeds": seeds, "results": {}}

    for regime in regimes:
        labels_dir = Path(args.targets_root) / f"regime_{regime}"
        artifacts = load_label_artifacts(labels_dir)
        nested["results"][regime] = {}
        traces[regime] = {}
        for seed in seeds:
            shared = dict(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                accepted_accuracy_min_coverage=float(args.accepted_accuracy_min_coverage),
                coverage_min_accepted_accuracy=float(args.coverage_min_accepted_accuracy),
            )

            cfg_v2 = LearningConfig(feature_set="v2", train_pairwise=True, train_pairwise_defer_classifier=False, **shared)
            met_v2 = evaluate_models(train_models(prepare_learning_tables(artifacts, cfg_v2), cfg_v2), prepare_learning_tables(artifacts, cfg_v2), cfg_v2).get("pairwise", {})

            cfg_v3 = LearningConfig(feature_set="v3", train_pairwise=True, train_pairwise_defer_classifier=False, **shared)
            met_v3 = evaluate_models(train_models(prepare_learning_tables(artifacts, cfg_v3), cfg_v3), prepare_learning_tables(artifacts, cfg_v3), cfg_v3).get("pairwise", {})

            cfg_defer_heur = LearningConfig(
                feature_set="v3",
                train_pairwise=False,
                train_pairwise_defer_classifier=True,
                defer_target_mode="heuristic",
                defer_calibration="none",
                **shared,
            )
            eval_heur, trace_heur = _run_setting(artifacts, out_dir, regime, seed, cfg_defer_heur)
            met_defer_heur = eval_heur.get("pairwise_defer_classifier", {})

            cfg_defer_oracle = LearningConfig(
                feature_set="v3",
                train_pairwise=False,
                train_pairwise_defer_classifier=True,
                defer_target_mode="oracle_proxy",
                defer_calibration="none",
                **shared,
            )
            eval_oracle, trace_oracle = _run_setting(artifacts, out_dir, regime, seed, cfg_defer_oracle)
            met_defer_oracle = eval_oracle.get("pairwise_defer_classifier", {})

            models = {
                "pairwise_logreg_v2": _extract_pairwise(met_v2),
                "pairwise_logreg_v3": _extract_pairwise(met_v3),
                "pairwise_defer_v3_heuristic": _extract_defer(met_defer_heur),
                "pairwise_defer_v3_oracle_proxy": _extract_defer(met_defer_oracle),
            }
            trace_models = {
                "pairwise_defer_v3_heuristic": trace_heur,
                "pairwise_defer_v3_oracle_proxy": trace_oracle,
            }

            if args.include_calibrated:
                cfg_defer_cal = LearningConfig(
                    feature_set="v3",
                    train_pairwise=False,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="oracle_proxy",
                    defer_calibration="temperature",
                    **shared,
                )
                eval_cal, trace_cal = _run_setting(artifacts, out_dir, regime, seed, cfg_defer_cal)
                models["pairwise_defer_v3_oracle_proxy_calibrated"] = _extract_defer(eval_cal.get("pairwise_defer_classifier", {}))
                trace_models["pairwise_defer_v3_oracle_proxy_calibrated"] = trace_cal

            nested["results"][regime][str(seed)] = models
            traces[regime][str(seed)] = trace_models
            for model_name, model_metrics in models.items():
                rows.append({"regime": regime, "seed": seed, "model": model_name, **model_metrics})

    aggregate: dict[str, Any] = {}
    for regime in regimes:
        aggregate[regime] = {}
        model_names = sorted({r["model"] for r in rows if r["regime"] == regime})
        for model_name in model_names:
            subset = [r for r in rows if r["regime"] == regime and r["model"] == model_name]
            if not subset:
                continue
            keys = [k for k in subset[0].keys() if k not in {"regime", "seed", "model"} and subset[0][k] is not None]
            aggregate[regime][model_name] = {k: _mean([float(s.get(k, 0.0)) for s in subset]) for k in keys}

    summary = {
        "run_id": run_id,
        "aggregate": aggregate,
        "rows": rows,
        "threshold_traces": traces,
        "safe_interpretation": (
            "Oracle-proxy defer labels and calibration are bounded approximations to budget-aware selective decisions; "
            "they should be interpreted as supervision and operating-point diagnostics, not exact global oracle control."
        ),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "structured_ambiguity_results.json").write_text(json.dumps(nested, indent=2), encoding="utf-8")

    md = [
        "# Structured ambiguity experiment",
        "",
        f"- run_id: `{run_id}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        "",
        "## Main comparison table (aggregate)",
        "",
    ]
    for regime in regimes:
        md.append(f"### Regime `{regime}`")
        for model_name, vals in aggregate.get(regime, {}).items():
            md.append(f"#### {model_name}")
            for k, v in vals.items():
                md.append(f"- {k}: `{v:.6f}`")
            md.append("")

    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "output_dir": str(out_dir), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
