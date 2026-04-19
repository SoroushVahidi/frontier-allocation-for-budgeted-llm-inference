#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

METHODS = [
    "self_consistency_3",
    "broad_diversity_aggregation_v1",
    "broad_diversity_aggregation_strong_v1",
    "marginal_coverage_diversity_v1",
    "duplicate_aware_aggregation_commit_v1",
]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _mistake_category(row: dict[str, Any]) -> str:
    unique_groups = int(row.get("unique_answer_groups_seen", 0))
    margin = _to_float(row.get("answer_group_margin", 0.0))
    support_frac = _to_float(row.get("group_support_fraction", 0.0))
    unstable_commit = bool(row.get("unstable_commit_flag", False))

    if unstable_commit:
        return "unstable_commit_selection"
    if unique_groups <= 1:
        return "insufficient_diversity_realized"
    if support_frac >= 0.75:
        return "aggregation_concentration_failure"
    if support_frac < 0.55 or margin < 0.12:
        return "ranking_error_despite_diversity"
    return "other_or_commit_timing"


def main() -> None:
    p = argparse.ArgumentParser(description="Duplicate-aware aggregation + answer-group commit pass")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=32)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/duplicate_aware_aggregation_commit_pass_20260418")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260418)
    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in budgets:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_broad_diversity_aggregation_methods=True,
                    include_marginal_coverage_diversity_methods=True,
                    include_duplicate_aware_aggregation_commit_methods=True,
                )
                strategies = {k: v for k, v in strategies.items() if k in METHODS}
                metrics, rows = evaluate_strategies_on_examples(examples, strategies)

                for method, m in metrics.items():
                    per_seed_method.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "accuracy": float(m["accuracy"]),
                        }
                    )

                for r in rows:
                    if r["strategy"] not in METHODS:
                        continue
                    meta = r.get("metadata") or {}
                    commit_checks = meta.get("commit_checks") or []
                    last_commit = commit_checks[-1] if commit_checks else {}
                    per_example_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": r["example_id"],
                            "method": r["strategy"],
                            "is_correct": bool(r["is_correct"]),
                            "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                            "group_support_fraction": _to_float(meta.get("group_support_fraction", 0.0)),
                            "answer_group_margin": _to_float(meta.get("answer_group_margin", 0.0)),
                            "top_group_readiness": _to_float(meta.get("top_group_readiness", 0.0)),
                            "mean_independence_discount": _to_float(meta.get("mean_independence_discount", 1.0)),
                            "duplicate_discount_applied_rate": _to_float(meta.get("duplicate_discount_applied_rate", 0.0)),
                            "mean_coverage_gain_on_expand": _to_float(meta.get("mean_coverage_gain_on_expand", 0.0)),
                            "mean_semantic_overlap_on_expand": _to_float(meta.get("mean_semantic_overlap_on_expand", 0.0)),
                            "aggregation_used": bool(meta.get("aggregation_used", False)),
                            "commit_triggered": bool(meta.get("commit_triggered", False)),
                            "unstable_commit_flag": bool(meta.get("unstable_commit_flag", False)),
                            "commit_checks_count": int(meta.get("commit_checks_count", 0)),
                            "last_one_step_value_estimate": _to_float(last_commit.get("one_step_value_estimate", 0.0)),
                            "last_top_group_support": _to_float(last_commit.get("top_group_support", 0.0)),
                            "last_second_group_support": _to_float(last_commit.get("second_group_support", 0.0)),
                            "last_answer_group_margin": _to_float(last_commit.get("answer_group_margin", 0.0)),
                        }
                    )

    by_method = defaultdict(list)
    by_dataset_method = defaultdict(list)
    for row in per_seed_method:
        by_method[row["method"]].append(row["accuracy"])
        by_dataset_method[(row["dataset"], row["method"])].append(row["accuracy"])

    overall = {m: {"mean_accuracy_over_budgets": _mean(v), "seed_stability_std": _std(v)} for m, v in by_method.items()}
    per_dataset = {
        ds: {
            m: {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}
            for (d2, m), vals in by_dataset_method.items()
            if d2 == ds
        }
        for ds in datasets
    }

    aligned = defaultdict(dict)
    for r in per_example_rows:
        key = (r["dataset"], r["seed"], r["budget"], r["example_id"])
        aligned[key][r["method"]] = r
    aligned_rows = [row for row in aligned.values() if all(m in row for m in METHODS)]

    best_new = "duplicate_aware_aggregation_commit_v1"
    broad_main = "broad_diversity_aggregation_strong_v1"
    sc = "self_consistency_3"

    mistake_counts = {m: Counter() for m in METHODS}
    for row in aligned_rows:
        for method in METHODS:
            if not row[method]["is_correct"]:
                mistake_counts[method].update([_mistake_category(row[method])])

    def _rows(method: str) -> list[dict[str, Any]]:
        return [r for r in per_example_rows if r["method"] == method]

    support_diag = {
        m: {
            "mean_group_support_fraction": _mean([_to_float(r["group_support_fraction"]) for r in _rows(m)]),
            "mean_answer_group_margin": _mean([_to_float(r["answer_group_margin"]) for r in _rows(m)]),
            "mean_top_group_readiness": _mean([_to_float(r["top_group_readiness"]) for r in _rows(m)]),
            "mean_independence_discount": _mean([_to_float(r["mean_independence_discount"]) for r in _rows(m)]),
            "mean_duplicate_discount_applied_rate": _mean([_to_float(r["duplicate_discount_applied_rate"]) for r in _rows(m)]),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in _rows(m)]),
            "aggregation_used_rate": _mean([1.0 if r["aggregation_used"] else 0.0 for r in _rows(m)]),
        }
        for m in METHODS
    }

    commit_diag = {
        m: {
            "commit_trigger_rate": _mean([1.0 if r["commit_triggered"] else 0.0 for r in _rows(m)]),
            "unstable_commit_rate": _mean([1.0 if r["unstable_commit_flag"] else 0.0 for r in _rows(m)]),
            "mean_commit_checks_count": _mean([float(r["commit_checks_count"]) for r in _rows(m)]),
            "mean_last_one_step_value_estimate": _mean([_to_float(r["last_one_step_value_estimate"]) for r in _rows(m)]),
            "mean_last_answer_group_margin": _mean([_to_float(r["last_answer_group_margin"]) for r in _rows(m)]),
        }
        for m in METHODS
    }

    aggregate_summary = {
        "overall_method_summary": overall,
        "gap_to_self_consistency_3": {
            m: float(overall[sc]["mean_accuracy_over_budgets"] - overall[m]["mean_accuracy_over_budgets"])
            for m in METHODS
            if m != sc
        },
        "gap_vs_current_broad_candidate": {
            m: float(overall[broad_main]["mean_accuracy_over_budgets"] - overall[m]["mean_accuracy_over_budgets"])
            for m in METHODS
            if m != broad_main
        },
        "target_bottleneck_rates": {
            m: {
                "aggregation_concentration_failure_rate": float(
                    mistake_counts[m].get("aggregation_concentration_failure", 0) / max(1, sum(mistake_counts[m].values()))
                ),
                "ranking_error_despite_diversity_rate": float(
                    mistake_counts[m].get("ranking_error_despite_diversity", 0) / max(1, sum(mistake_counts[m].values()))
                ),
                "unstable_commit_selection_rate": float(
                    mistake_counts[m].get("unstable_commit_selection", 0) / max(1, sum(mistake_counts[m].values()))
                ),
            }
            for m in METHODS
        },
        "headline": {
            "new_variant_mean": float(overall[best_new]["mean_accuracy_over_budgets"]),
            "current_broad_mean": float(overall[broad_main]["mean_accuracy_over_budgets"]),
            "sc3_mean": float(overall[sc]["mean_accuracy_over_budgets"]),
            "broad_gap_to_sc_narrowed": bool(
                abs(overall[best_new]["mean_accuracy_over_budgets"] - overall[sc]["mean_accuracy_over_budgets"])
                < abs(overall[broad_main]["mean_accuracy_over_budgets"] - overall[sc]["mean_accuracy_over_budgets"])
            ),
        },
    }

    def _shift(reference: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for cat in [
            "aggregation_concentration_failure",
            "ranking_error_despite_diversity",
            "unstable_commit_selection",
            "insufficient_diversity_realized",
            "other_or_commit_timing",
        ]:
            out[cat] = {
                f"{reference}_count": int(mistake_counts[reference].get(cat, 0)),
                "new_count": int(mistake_counts[best_new].get(cat, 0)),
                "delta_new_minus_reference": int(mistake_counts[best_new].get(cat, 0) - mistake_counts[reference].get(cat, 0)),
            }
        return out

    method_definition = {
        "method_name": best_new,
        "family": "broad_diversity_aggregation",
        "support_discount_rule": "support_weight = process_quality * target_completion * independence_discount",
        "independence_discount_rule": "max(duplicate_discount_floor, 1 - duplicate_discount_strength * max_same_group_profile_similarity)",
        "group_commit_rule": "commit when top group discounted support, margin, and readiness clear thresholds and one-step continuation estimate is low",
        "key_thresholds": {
            "commit_margin_threshold": 0.17,
            "commit_top_support_threshold": 0.61,
            "commit_readiness_threshold": 0.57,
            "continue_one_step_value_threshold": 0.64,
        },
    }

    support_discount_schema = {
        "branch_weight": "process_quality * target_completion * independence_discount",
        "process_quality_source": "canonical objective stack surrogate",
        "target_completion_source": "canonical objective stack surrogate",
        "independence_discount": {
            "formula": "max(0.22, 1 - 0.75 * max_same_group_similarity)",
            "similarity": "jaccard over support-profile features",
        },
    }

    commit_rule_schema = {
        "commit_when_all": [
            "actions >= min_actions_before_commit_check",
            "top_group_support >= 0.61",
            "answer_group_margin >= 0.17",
            "top_group_readiness >= 0.57",
            "one_step_value_estimate <= 0.64",
        ],
        "continue_when": [
            "answer_group_margin weak",
            "or one_step_value_estimate high",
        ],
    }

    residual_tax = {
        "method": best_new,
        "residual_loss_counts": dict(mistake_counts[best_new]),
        "residual_loss_total": int(sum(mistake_counts[best_new].values())),
    }

    commands_md = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Command run",
            f"- python scripts/run_duplicate_aware_aggregation_commit_pass_20260418.py --datasets {','.join(datasets)} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
            "",
            "## Assumptions",
            "- This pass stays inside the broad diversity/aggregation family.",
            "- Evaluated in simulator mode with fixed-budget next-step allocation.",
            "",
            "## Caveats",
            "- Bounded real-model confirmation with Cohere/Gemini only was not executed here due unavailable provider credentials.",
            "- Mistake grouping is heuristic, based on logged aggregation and commit diagnostics.",
        ]
    )

    manifest = {
        "run_name": "duplicate_aware_aggregation_commit_pass_20260418",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_duplicate_aware_aggregation_commit_pass_20260418.py",
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": METHODS,
    }

    outputs = {
        "manifest.json": manifest,
        "method_definition.json": method_definition,
        "methods_compared.json": {
            "methods": METHODS,
            "new_variant": best_new,
            "current_broad_candidate": broad_main,
        },
        "datasets_compared.json": {"datasets": datasets, "seeds": seeds, "budgets": budgets, "subset_size": args.subset_size},
        "support_discount_schema.json": support_discount_schema,
        "commit_rule_schema.json": commit_rule_schema,
        "aggregate_comparison_summary.json": aggregate_summary,
        "per_dataset_tables.json": {"per_dataset": per_dataset},
        "support_diagnostics.json": support_diag,
        "commit_margin_diagnostics.json": commit_diag,
        "mistake_group_shift_summary.json": {
            "vs_broad_diversity_aggregation_strong_v1": _shift(broad_main),
            "vs_self_consistency_3": _shift(sc),
        },
        "residual_loss_taxonomy.json": residual_tax,
    }

    for name, data in outputs.items():
        (out_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_md + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
