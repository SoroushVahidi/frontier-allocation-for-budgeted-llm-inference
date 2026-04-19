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
    "selective_sc_hybrid_v1",
    "broad_diversity_aggregation_strong_v1",
    "broad_diversity_aggregation_v1",
    "marginal_coverage_diversity_v1",
]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _mistake_category(row: dict[str, Any]) -> str:
    unique_groups = int(row.get("unique_answer_groups_seen", 0))
    support_frac = float(row.get("group_support_fraction", 0.0))
    overlap = float(row.get("mean_semantic_overlap_on_expand", 0.0))
    coverage = float(row.get("mean_coverage_gain_on_expand", 0.0))

    if unique_groups <= 1:
        return "insufficient_diversity_realized"
    if support_frac < 0.45 or (overlap >= 0.72 and coverage <= 0.28):
        return "bad_diversity_realized"
    if support_frac < 0.60:
        return "value_ranking_error_despite_diversity"
    return "other_or_commit_timing"


def main() -> None:
    p = argparse.ArgumentParser(description="Marginal coverage / overlap pass inside broad diversity family")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=32)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/marginal_coverage_diversity_pass_20260418")
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
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                    include_marginal_coverage_diversity_methods=True,
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
                            "avg_actions": float(m["avg_actions"]),
                        }
                    )

                for r in rows:
                    if r["strategy"] not in METHODS:
                        continue
                    meta = r.get("metadata") or {}
                    per_example_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": r["example_id"],
                            "method": r["strategy"],
                            "is_correct": bool(r["is_correct"]),
                            "predicted_answer": r.get("prediction"),
                            "answer_support_entropy": float(meta.get("answer_support_entropy", 0.0)),
                            "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                            "group_support_fraction": float(meta.get("group_support_fraction", 0.0)),
                            "aggregation_used": bool(meta.get("aggregation_used", False)),
                            "duplicate_penalty_applied_rate": float(meta.get("duplicate_penalty_applied_rate", 0.0)),
                            "mean_diversity_bonus_on_expand": float(meta.get("mean_diversity_bonus_on_expand", 0.0)),
                            "mean_coverage_gain_on_expand": float(meta.get("mean_coverage_gain_on_expand", 0.0)),
                            "mean_semantic_overlap_on_expand": float(meta.get("mean_semantic_overlap_on_expand", 0.0)),
                            "forced_explore_rate": float(meta.get("forced_explore_rate", 0.0)),
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

    def _acc(method: str) -> float:
        vals = [1.0 if row[method]["is_correct"] else 0.0 for row in aligned_rows]
        return _mean(vals)

    mistake_counts = {m: Counter() for m in METHODS}
    for row in aligned_rows:
        for method in METHODS:
            if not row[method]["is_correct"]:
                mistake_counts[method].update([_mistake_category(row[method])])

    broad_main = "broad_diversity_aggregation_strong_v1"
    new_method = "marginal_coverage_diversity_v1"
    sc = "self_consistency_3"

    shift_vs_broad = {}
    for cat in ["insufficient_diversity_realized", "bad_diversity_realized", "value_ranking_error_despite_diversity", "other_or_commit_timing"]:
        shift_vs_broad[cat] = {
            "broad_count": int(mistake_counts[broad_main].get(cat, 0)),
            "marginal_count": int(mistake_counts[new_method].get(cat, 0)),
            "delta_marginal_minus_broad": int(mistake_counts[new_method].get(cat, 0) - mistake_counts[broad_main].get(cat, 0)),
        }

    shift_vs_sc = {}
    for cat in ["insufficient_diversity_realized", "bad_diversity_realized", "value_ranking_error_despite_diversity", "other_or_commit_timing"]:
        shift_vs_sc[cat] = {
            "self_consistency_count": int(mistake_counts[sc].get(cat, 0)),
            "marginal_count": int(mistake_counts[new_method].get(cat, 0)),
            "delta_marginal_minus_sc": int(mistake_counts[new_method].get(cat, 0) - mistake_counts[sc].get(cat, 0)),
        }

    def _method_rows(method: str) -> list[dict[str, Any]]:
        return [r for r in per_example_rows if r["method"] == method]

    diversity_diag = {
        m: {
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in _method_rows(m)]),
            "mean_answer_support_entropy": _mean([float(r["answer_support_entropy"]) for r in _method_rows(m)]),
            "mean_group_support_fraction": _mean([float(r["group_support_fraction"]) for r in _method_rows(m)]),
            "aggregation_used_rate": _mean([1.0 if r["aggregation_used"] else 0.0 for r in _method_rows(m)]),
            "useful_answer_distinct_branch_rate": _mean(
                [1.0 if int(r["unique_answer_groups_seen"]) >= 2 and float(r["group_support_fraction"]) >= 0.45 else 0.0 for r in _method_rows(m)]
            ),
        }
        for m in METHODS
    }

    overlap_diag = {
        m: {
            "mean_semantic_overlap_on_expand": _mean([float(r["mean_semantic_overlap_on_expand"]) for r in _method_rows(m)]),
            "mean_coverage_gain_on_expand": _mean([float(r["mean_coverage_gain_on_expand"]) for r in _method_rows(m)]),
            "mean_duplicate_penalty_applied_rate": _mean([float(r["duplicate_penalty_applied_rate"]) for r in _method_rows(m)]),
            "mean_diversity_bonus_on_expand": _mean([float(r["mean_diversity_bonus_on_expand"]) for r in _method_rows(m)]),
        }
        for m in METHODS
    }

    aggregate_summary = {
        "overall_method_summary": overall,
        "gap_to_self_consistency_3": {
            m: float(overall["self_consistency_3"]["mean_accuracy_over_budgets"] - overall[m]["mean_accuracy_over_budgets"])
            for m in METHODS
            if m != "self_consistency_3"
        },
        "gap_vs_current_broad_candidate": {
            m: float(overall[broad_main]["mean_accuracy_over_budgets"] - overall[m]["mean_accuracy_over_budgets"])
            for m in METHODS
            if m != broad_main
        },
        "headline": {
            "aligned_accuracy_self_consistency_3": _acc("self_consistency_3"),
            "aligned_accuracy_broad_diversity_aggregation_strong_v1": _acc("broad_diversity_aggregation_strong_v1"),
            "aligned_accuracy_marginal_coverage_diversity_v1": _acc("marginal_coverage_diversity_v1"),
            "broad_gap_to_sc_narrowed": bool(
                abs(overall[new_method]["mean_accuracy_over_budgets"] - overall[sc]["mean_accuracy_over_budgets"])
                < abs(overall[broad_main]["mean_accuracy_over_budgets"] - overall[sc]["mean_accuracy_over_budgets"])
            ),
        },
    }

    method_definition = {
        "method_name": new_method,
        "family": "broad_diversity_aggregation",
        "base_utility": "continuation_value from canonical branch scorer",
        "scoring_rule": "priority = continuation + diversity_bonus + lambda*coverage_gain - mu*semantic_overlap - duplicate_cost",
        "lambda_coverage_weight": 0.24,
        "mu_overlap_weight": 0.16,
        "coverage_gain_components": {
            "group_undercoverage": "1 - group_mass/(active+supported total)",
            "new_group_bonus": "1 if answer group is not yet covered",
            "profile_novelty": "1 - max_similarity to same-group support profiles",
        },
        "semantic_overlap_components": {
            "same_group_similarity": "max jaccard similarity against completed profiles in same normalized-answer group",
            "global_similarity": "max jaccard similarity against all completed profiles",
        },
        "support_profile_features": [
            "normalized answer group",
            "depth bucket",
            "score bucket",
            "verification bucket",
            "lightweight reasoning-structure markers (equation/case-analysis/conclusion/operator hints)",
        ],
    }

    coverage_overlap_schema = {
        "coverage_gain_formula": "0.50*group_undercoverage + 0.30*new_group_bonus + 0.20*profile_novelty",
        "semantic_overlap_formula": "0.65*same_group_max_similarity + 0.35*global_max_similarity",
        "priority_formula": "continuation + diversity_bonus + 0.24*coverage_gain - 0.16*semantic_overlap - duplicate_cost",
        "note": "Coverage/overlap terms are computed from normalized answer groups and support profiles; not raw lexical distance.",
    }

    residual_taxonomy = {
        "reference_method": new_method,
        "counts": dict(mistake_counts[new_method]),
        "total_errors": int(sum(mistake_counts[new_method].values())),
    }

    commands_assumptions_caveats = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Command run",
            f"- python scripts/run_marginal_coverage_diversity_pass_20260418.py --datasets {','.join(datasets)} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
            "",
            "## Assumptions",
            "- This pass stays inside the existing broad diversity/aggregation family.",
            "- Evaluated in simulator mode using the canonical fixed-budget setup.",
            "",
            "## Caveats",
            "- Real-model confirmation (Cohere/Gemini only) was not executed in this pass due bounded local runtime focus and unavailable provider credentials in this environment.",
            "- Mistake-group mapping is heuristic and based on logged branch-level diagnostics.",
        ]
    )

    manifest = {
        "run_name": "marginal_coverage_diversity_pass_20260418",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_marginal_coverage_diversity_pass_20260418.py",
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": METHODS,
    }

    outputs = {
        "manifest.json": manifest,
        "method_definition.json": method_definition,
        "methods_compared.json": {"methods": METHODS, "current_broad_main_candidate": broad_main, "new_variant": new_method},
        "datasets_compared.json": {"datasets": datasets, "seeds": seeds, "budgets": budgets, "subset_size": args.subset_size},
        "coverage_overlap_schema.json": coverage_overlap_schema,
        "aggregate_comparison_summary.json": aggregate_summary,
        "per_dataset_tables.json": {"per_dataset": per_dataset},
        "diversity_diagnostics.json": diversity_diag,
        "overlap_suppression_diagnostics.json": overlap_diag,
        "mistake_group_shift_summary.json": {
            "vs_broad_diversity_aggregation_strong_v1": shift_vs_broad,
            "vs_self_consistency_3": shift_vs_sc,
        },
        "residual_loss_taxonomy.json": residual_taxonomy,
    }

    for name, data in outputs.items():
        (out_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_assumptions_caveats + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
