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
    "adaptive_min_expand_1",
    "intermediate_trap_aware_near_tie_v1",
    "selective_sc_hybrid_v1",
    "broad_diversity_aggregation_v1",
    "broad_diversity_aggregation_strong_v1",
]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _load_prev_hybrid_failure() -> dict[str, Any]:
    prev = REPO_ROOT / "outputs" / "self_consistency_hybrid_broad_eval_20260418" / "failure_gap_taxonomy.json"
    if prev.exists():
        return json.loads(prev.read_text(encoding="utf-8"))
    return {
        "remaining_gap_reason_counts": {
            "insufficient_diversity_or_aggregation": "unknown",
            "over_conservative_gating": "unknown",
        },
        "note": "prior broad hybrid output not found in this checkout; using repo-stated diagnosis",
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Broad diversity/aggregation method pass")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/broad_diversity_aggregation_pass_20260418")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    prev_failure = _load_prev_hybrid_failure()

    per_seed_method: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []

    rng_master = random.Random(20260418)

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
                )
                strategies = {k: v for k, v in strategies.items() if k in METHODS}
                metrics, rows = evaluate_strategies_on_examples(examples, strategies)

                for m, vals in metrics.items():
                    per_seed_method.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": m,
                            "accuracy": float(vals["accuracy"]),
                            "avg_actions": float(vals["avg_actions"]),
                            "n_eval_examples": int(vals["n_examples"]),
                            "budget_exhaustion_rate": float(vals["budget_exhaustion_rate"]),
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
                            "actions_used": int(r["actions_used"]),
                            "hard_case_active": bool(meta.get("hard_case_active", False)),
                            "near_tie": bool(meta.get("near_tie", False)),
                            "continuation_completion_disagree": bool(meta.get("continuation_completion_disagree", False)),
                            "consensus_override": bool(meta.get("consensus_override", False)),
                            "answer_support_entropy": float(meta.get("answer_support_entropy", 0.0)),
                            "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                            "group_support_fraction": float(meta.get("group_support_fraction", 0.0)),
                            "aggregation_used": bool(meta.get("aggregation_used", False)),
                        }
                    )

    # Group rows by (dataset,seed,budget,example)
    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in per_example_rows:
        key = (r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"])
        aligned[key][r["method"]] = r

    aligned_rows = [r for r in aligned.values() if all(m in r for m in METHODS)]

    # Overall/per-dataset/per-budget metrics
    by_method = defaultdict(list)
    by_method_dataset = defaultdict(list)
    by_method_budget = defaultdict(list)
    for r in per_seed_method:
        by_method[r["method"]].append(float(r["accuracy"]))
        by_method_dataset[(r["method"], r["dataset"])].append(float(r["accuracy"]))
        by_method_budget[(r["method"], int(r["budget"]))].append(float(r["accuracy"]))

    overall = {
        method: {
            "mean_accuracy_over_budgets": _mean(vals),
            "seed_stability_std": _std(vals),
        }
        for method, vals in by_method.items()
    }

    per_dataset: dict[str, dict[str, dict[str, float]]] = {}
    for (method, ds), vals in by_method_dataset.items():
        per_dataset.setdefault(ds, {})[method] = {
            "mean_accuracy": _mean(vals),
            "seed_stability_std": _std(vals),
        }

    budget_table: dict[str, dict[str, dict[str, float]]] = {}
    for (method, b), vals in by_method_budget.items():
        budget_table.setdefault(str(b), {})[method] = {
            "mean_accuracy": _mean(vals),
            "std_accuracy": _std(vals),
        }

    # Hard slices (reuse hybrid near-tie/disagreement markers to keep comparability)
    def _slice_acc(method: str, cond_key: str) -> float:
        vals = [int(row[method]["is_correct"]) for row in aligned_rows if bool(row["selective_sc_hybrid_v1"].get(cond_key, False))]
        return float(sum(vals) / len(vals)) if vals else 0.0

    hard_slice = {
        "near_tie": {m: _slice_acc(m, "near_tie") for m in METHODS},
        "disagreement": {m: _slice_acc(m, "continuation_completion_disagree") for m in METHODS},
        "hard_case_active": {m: _slice_acc(m, "hard_case_active") for m in METHODS},
    }

    # Gap reductions
    sc = overall["self_consistency_3"]["mean_accuracy_over_budgets"]
    baseline = overall["adaptive_min_expand_1"]["mean_accuracy_over_budgets"]
    hybrid = overall["selective_sc_hybrid_v1"]["mean_accuracy_over_budgets"]
    broad = overall["broad_diversity_aggregation_v1"]["mean_accuracy_over_budgets"]
    broad_strong = overall["broad_diversity_aggregation_strong_v1"]["mean_accuracy_over_budgets"]

    def _gap(v: float) -> float:
        return float(sc - v)

    best_broad_name = "broad_diversity_aggregation_v1" if broad >= broad_strong else "broad_diversity_aggregation_strong_v1"
    best_broad = max(broad, broad_strong)

    gap_summary = {
        "gap_to_self_consistency": {
            "adaptive_min_expand_1": _gap(baseline),
            "selective_sc_hybrid_v1": _gap(hybrid),
            "broad_diversity_aggregation_v1": _gap(broad),
            "broad_diversity_aggregation_strong_v1": _gap(broad_strong),
            "best_broad_variant": best_broad_name,
            "best_broad_gap": _gap(best_broad),
        },
        "gap_reduction_vs_adaptive_min_expand_1": {
            "broad_diversity_aggregation_v1": float(broad - baseline),
            "broad_diversity_aggregation_strong_v1": float(broad_strong - baseline),
        },
        "gap_reduction_vs_selective_sc_hybrid_v1": {
            "broad_diversity_aggregation_v1": float(broad - hybrid),
            "broad_diversity_aggregation_strong_v1": float(broad_strong - hybrid),
        },
        "material_narrowing_flag": bool((_gap(hybrid) - _gap(best_broad)) >= 0.02),
    }

    # Diversity behavior diagnostics
    broad_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_v1"]
    broad_strong_rows = [r for r in per_example_rows if r["method"] == "broad_diversity_aggregation_strong_v1"]

    def _div_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
        n = max(1, len(rows))
        return {
            "n_examples": len(rows),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in rows]),
            "mean_answer_support_entropy": _mean([float(r["answer_support_entropy"]) for r in rows]),
            "aggregation_used_rate": float(sum(int(bool(r["aggregation_used"])) for r in rows) / n),
            "mean_group_support_fraction": _mean([float(r["group_support_fraction"]) for r in rows]),
        }

    diversity_behavior = {
        "broad_diversity_aggregation_v1": _div_summary(broad_rows),
        "broad_diversity_aggregation_strong_v1": _div_summary(broad_strong_rows),
    }

    answer_support_diag = {
        "best_broad_variant": best_broad_name,
        "best_broad_metrics": diversity_behavior[best_broad_name],
        "paired_vs_selective_sc_hybrid": {
            "hybrid_accuracy": overall["selective_sc_hybrid_v1"]["mean_accuracy_over_budgets"],
            "best_broad_accuracy": best_broad,
            "accuracy_delta": float(best_broad - overall["selective_sc_hybrid_v1"]["mean_accuracy_over_budgets"]),
        },
    }

    # Failure taxonomy for best broad variant vs SC
    failure_reasons = Counter()
    broad_beats_hybrid = 0
    broad_loses_sc = 0
    for row in aligned_rows:
        sc_ok = bool(row["self_consistency_3"]["is_correct"])
        hy_ok = bool(row["selective_sc_hybrid_v1"]["is_correct"])
        br_ok = bool(row[best_broad_name]["is_correct"])
        if br_ok and not hy_ok:
            broad_beats_hybrid += 1
        if (not br_ok) and sc_ok:
            broad_loses_sc += 1
            if int(row[best_broad_name].get("unique_answer_groups_seen", 0)) <= 1:
                failure_reasons.update(["insufficient_global_diversity_realized"])
            elif float(row[best_broad_name].get("group_support_fraction", 0.0)) < 0.45:
                failure_reasons.update(["weak_answer_support_concentration"])
            else:
                failure_reasons.update(["value_ranking_error_despite_diversity"])

    failure_gap = {
        "previous_bounded_hybrid_failure_reference": prev_failure,
        "best_broad_variant": best_broad_name,
        "where_best_broad_beats_selective_hybrid": {
            "count": int(broad_beats_hybrid),
            "rate": float(broad_beats_hybrid / max(1, len(aligned_rows))),
        },
        "where_best_broad_still_loses_to_self_consistency": {
            "count": int(broad_loses_sc),
            "rate": float(broad_loses_sc / max(1, len(aligned_rows))),
        },
        "remaining_gap_reason_counts": dict(failure_reasons),
    }

    method_def = {
        "pass_name": "broad_diversity_aggregation_pass_20260418",
        "design_requirements_from_previous_pass": [
            "bounded local hard-case correction was insufficient for broad competition",
            "insufficient_diversity_or_aggregation remained dominant",
            "need global, not only near-tie, diversity/aggregation behavior",
        ],
        "implemented_variants": {
            "broad_diversity_aggregation_v1": {
                "allocation_policy": "continuation_value base + diversity bonus + duplicate-answer suppression",
                "final_policy": "answer-group aggregation (support + value weighted)",
                "commit_behavior": "global commit-delay while support concentration is weak",
            },
            "broad_diversity_aggregation_strong_v1": {
                "allocation_policy": "same family with stronger diversity pressure",
                "final_policy": "higher answer-support weight at final aggregation",
                "commit_behavior": "longer commit-delay floor",
            },
        },
        "how_differs_from_bounded_local_hybrid": [
            "diversity is active throughout allocation, not only hard-case fallback",
            "answer aggregation is default final policy, not local override",
            "commit-delay is global support-aware rather than near-tie-only gating",
        ],
        "canonical_stack_preserved": ["process_quality", "target_completion", "continuation_value"],
        "extensions": ["answer_support", "diversity_value"],
    }

    agg_summary = {
        "overall_method_summary": overall,
        "hard_slice_summary": hard_slice,
        "gap_summary": gap_summary,
        "conclusion": (
            "best broad diversity variant materially narrows gap to self_consistency_3"
            if gap_summary["material_narrowing_flag"]
            else "best broad diversity variant improves but does not materially narrow gap to self_consistency_3"
        ),
    }

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_broad_diversity_aggregation_pass_20260418.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": METHODS,
    }

    methods_compared = {"methods": METHODS, "best_broad_variant": best_broad_name}
    datasets_compared = {"datasets": datasets, "seeds": seeds, "budgets": budgets, "subset_size": args.subset_size}

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "method_definition.json").write_text(json.dumps(method_def, indent=2) + "\n", encoding="utf-8")
    (out_dir / "methods_compared.json").write_text(json.dumps(methods_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "datasets_compared.json").write_text(json.dumps(datasets_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "aggregate_comparison_summary.json").write_text(json.dumps(agg_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_dataset_tables.json").write_text(json.dumps({"per_dataset": per_dataset, "budget_table": budget_table}, indent=2) + "\n", encoding="utf-8")
    (out_dir / "gap_reduction_summary.json").write_text(json.dumps(gap_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "diversity_behavior_summary.json").write_text(json.dumps(diversity_behavior, indent=2) + "\n", encoding="utf-8")
    (out_dir / "answer_support_diagnostics.json").write_text(json.dumps(answer_support_diag, indent=2) + "\n", encoding="utf-8")
    (out_dir / "failure_gap_taxonomy.json").write_text(json.dumps(failure_gap, indent=2) + "\n", encoding="utf-8")

    commands_md = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Command run",
            f"- python scripts/run_broad_diversity_aggregation_pass_20260418.py --datasets {','.join(datasets)} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
            "",
            "## Assumptions",
            "- Same simulator-mode broad setting as previous light broad pass for comparability.",
            "- New variants preserve fixed-budget branch-allocation framing and continuation-value base scoring.",
            "",
            "## Caveats",
            "- Light pilot subsets; not final paper-scale absolute benchmark.",
            "- Results should be interpreted as broad directional evidence and ranking movement.",
        ]
    )
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_md + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "best_broad_variant": best_broad_name}, indent=2))


if __name__ == "__main__":
    main()
