#!/usr/bin/env python3
"""Bounded defer-conditioned fallback experiment."""

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
    p = argparse.ArgumentParser(description="Run defer-conditioned fallback experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="")
    p.add_argument("--seeds", default="17,29,43")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--include-specialist", action="store_true")
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    return sum(vals) / max(1, len(vals))


def _extract_defer(m: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "accepted_only_accuracy_test",
        "coverage_test",
        "resolved_accuracy_test",
        "resolved_coverage_test",
        "unresolved_rate_after_fallback_test",
        "defer_f1_test",
        "near_tie_resolved_accuracy_test",
        "adjacent_rank_resolved_accuracy_test",
        "exact_promoted_hard_region_resolved_accuracy_test",
        "fallback_subset_accuracy",
        "fallback_gain_over_binary_backup",
    ]
    return {k: float(m.get(k, 0.0)) for k in keys}


def _extract_pairwise(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted_only_accuracy_test": float(m.get("pairwise_accuracy_test", 0.0)),
        "coverage_test": 1.0,
        "resolved_accuracy_test": float(m.get("pairwise_accuracy_test", 0.0)),
        "resolved_coverage_test": 1.0,
        "unresolved_rate_after_fallback_test": 0.0,
        "defer_f1_test": 0.0,
        "near_tie_resolved_accuracy_test": float(m.get("near_tie_pairwise_accuracy_test", 0.0)),
        "adjacent_rank_resolved_accuracy_test": float(m.get("adjacent_rank_pairwise_accuracy_test", 0.0)),
        "exact_promoted_hard_region_resolved_accuracy_test": float(m.get("exact_promoted_hard_region_pairwise_accuracy_test", 0.0)),
        "fallback_subset_accuracy": 0.0,
        "fallback_gain_over_binary_backup": 0.0,
    }


def _run_cfg(artifacts: dict[str, list[dict[str, Any]]], cfg: LearningConfig) -> dict[str, Any]:
    tables = prepare_learning_tables(artifacts, cfg)
    models = train_models(tables, cfg)
    return evaluate_models(models, tables, cfg)


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or f"defer_fallback_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [s.strip() for s in str(args.regimes).split(",") if s.strip()]

    rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {"run_id": run_id, "results": {}}

    for regime in regimes:
        artifacts = load_label_artifacts(Path(args.targets_root) / f"regime_{regime}")
        details["results"][regime] = {}
        for seed in seeds:
            common = dict(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                feature_set="v3",
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
            )

            eval_forced = _run_cfg(artifacts, LearningConfig(train_pairwise=True, train_pairwise_defer_classifier=False, **common))
            eval_defer_heur = _run_cfg(
                artifacts,
                LearningConfig(
                    train_pairwise=True,
                    train_pointwise=True,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="heuristic",
                    enable_defer_fallback=False,
                    **common,
                ),
            )
            eval_defer_oracle = _run_cfg(
                artifacts,
                LearningConfig(
                    train_pairwise=True,
                    train_pointwise=True,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="oracle_proxy",
                    enable_defer_fallback=False,
                    **common,
                ),
            )
            eval_pairwise_backup = _run_cfg(
                artifacts,
                LearningConfig(
                    train_pairwise=True,
                    train_pointwise=True,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="oracle_proxy",
                    enable_defer_fallback=True,
                    defer_fallback_policy="pairwise_binary_backup",
                    **common,
                ),
            )
            eval_pointwise_backup = _run_cfg(
                artifacts,
                LearningConfig(
                    train_pairwise=True,
                    train_pointwise=True,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="oracle_proxy",
                    enable_defer_fallback=True,
                    defer_fallback_policy="pointwise_value_backup",
                    **common,
                ),
            )
            eval_outside_backup = _run_cfg(
                artifacts,
                LearningConfig(
                    train_pairwise=True,
                    train_pointwise=True,
                    train_pairwise_defer_classifier=True,
                    defer_target_mode="oracle_proxy",
                    enable_defer_fallback=True,
                    defer_fallback_policy="outside_option_aware_backup",
                    **common,
                ),
            )

            model_rows = {
                "pairwise_logreg_v3_forced_binary": _extract_pairwise(eval_forced.get("pairwise", {})),
                "defer_v3_heuristic_defer_only": _extract_defer(eval_defer_heur.get("pairwise_defer_classifier", {})),
                "defer_v3_oracle_proxy_defer_only": _extract_defer(eval_defer_oracle.get("pairwise_defer_classifier", {})),
                "defer_v3_oracle_proxy_pairwise_binary_backup": _extract_defer(eval_pairwise_backup.get("pairwise_defer_classifier", {})),
                "defer_v3_oracle_proxy_pointwise_value_backup": _extract_defer(eval_pointwise_backup.get("pairwise_defer_classifier", {})),
                "defer_v3_oracle_proxy_outside_option_aware_backup": _extract_defer(eval_outside_backup.get("pairwise_defer_classifier", {})),
            }

            if args.include_specialist:
                eval_specialist = _run_cfg(
                    artifacts,
                    LearningConfig(
                        train_pairwise=True,
                        train_pointwise=True,
                        train_pairwise_defer_classifier=True,
                        train_pairwise_deferred_specialist=True,
                        defer_target_mode="oracle_proxy",
                        enable_defer_fallback=True,
                        defer_fallback_policy="specialized_hard_case_backup",
                        **common,
                    ),
                )
                model_rows["defer_v3_oracle_proxy_deferred_specialist_backup"] = _extract_defer(
                    eval_specialist.get("pairwise_defer_classifier", {})
                )
                model_rows["pairwise_deferred_specialist_eval"] = {
                    "accepted_only_accuracy_test": float(eval_specialist.get("pairwise_deferred_specialist", {}).get("deferred_subset_accuracy", 0.0)),
                    "coverage_test": 0.0,
                    "resolved_accuracy_test": float(eval_specialist.get("pairwise_deferred_specialist", {}).get("deferred_subset_accuracy", 0.0)),
                    "resolved_coverage_test": 0.0,
                    "unresolved_rate_after_fallback_test": 0.0,
                    "defer_f1_test": 0.0,
                    "near_tie_resolved_accuracy_test": float(eval_specialist.get("pairwise_deferred_specialist", {}).get("deferred_subset_near_tie_accuracy", 0.0)),
                    "adjacent_rank_resolved_accuracy_test": float(eval_specialist.get("pairwise_deferred_specialist", {}).get("deferred_subset_adjacent_rank_accuracy", 0.0)),
                    "exact_promoted_hard_region_resolved_accuracy_test": float(
                        eval_specialist.get("pairwise_deferred_specialist", {}).get("deferred_subset_exact_promoted_hard_region_accuracy", 0.0)
                    ),
                    "fallback_subset_accuracy": 0.0,
                    "fallback_gain_over_binary_backup": 0.0,
                }

            details["results"][regime][str(seed)] = model_rows
            for name, metrics in model_rows.items():
                rows.append({"regime": regime, "seed": seed, "model": name, **metrics})

    aggregate: dict[str, Any] = {}
    for regime in regimes:
        aggregate[regime] = {}
        model_names = sorted({r["model"] for r in rows if r["regime"] == regime})
        for model_name in model_names:
            subset = [r for r in rows if r["regime"] == regime and r["model"] == model_name]
            keys = [k for k in subset[0].keys() if k not in {"regime", "seed", "model"}]
            aggregate[regime][model_name] = {k: _mean([float(s.get(k, 0.0)) for s in subset]) for k in keys}

    summary = {
        "run_id": run_id,
        "regimes": regimes,
        "seeds": seeds,
        "aggregate": aggregate,
        "rows": rows,
        "safe_interpretation": "Fallback results are bounded policy-level comparisons over deferred states, not exact global oracle decisions.",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = ["# Defer-conditioned fallback experiment", "", f"- run_id: `{run_id}`", "", "## Aggregate comparison"]
    for regime, reg in aggregate.items():
        md.append(f"\n### Regime `{regime}`")
        for model_name, vals in reg.items():
            md.append(f"#### {model_name}")
            for k, v in vals.items():
                md.append(f"- {k}: `{v:.6f}`")
            md.append("")
    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "output_dir": str(out_dir), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
