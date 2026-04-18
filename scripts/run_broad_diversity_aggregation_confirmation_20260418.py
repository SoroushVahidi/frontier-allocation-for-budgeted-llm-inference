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



def _slice_acc(aligned_rows: list[dict[str, dict[str, Any]]], method: str, cond_key: str) -> float:
    vals = [int(row[method]["is_correct"]) for row in aligned_rows if bool(row["selective_sc_hybrid_v1"].get(cond_key, False))]
    return float(sum(vals) / len(vals)) if vals else 0.0



def main() -> None:
    p = argparse.ArgumentParser(description="Stricter confirmation pass for broad diversity/aggregation family")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=48)
    p.add_argument("--seeds", default="11,23,37,47,59")
    p.add_argument("--budgets", default="4,6,8,10")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/broad_diversity_aggregation_confirmation_20260418")
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
                            "avg_expansions": float(m["avg_expansions"]),
                            "avg_verifications": float(m["avg_verifications"]),
                            "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                            "n_eval_examples": int(m["n_examples"]),
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
                            "near_tie": bool(meta.get("near_tie", False)),
                            "disagreement": bool(meta.get("continuation_completion_disagree", False)),
                            "hard_case_active": bool(meta.get("hard_case_active", False)),
                            "answer_support_entropy": float(meta.get("answer_support_entropy", 0.0)),
                            "unique_answer_groups_seen": int(meta.get("unique_answer_groups_seen", 0)),
                            "group_support_fraction": float(meta.get("group_support_fraction", 0.0)),
                            "aggregation_used": bool(meta.get("aggregation_used", False)),
                            "forced_explore_rate": float(meta.get("forced_explore_rate", 0.0)),
                            "duplicate_penalty_applied_rate": float(meta.get("duplicate_penalty_applied_rate", 0.0)),
                            "mean_diversity_bonus_on_expand": float(meta.get("mean_diversity_bonus_on_expand", 0.0)),
                        }
                    )

    # aggregate seed/budget summaries
    by_method = defaultdict(list)
    by_dataset_method = defaultdict(list)
    by_budget_method = defaultdict(list)
    by_seed_budget_method = defaultdict(list)
    for row in per_seed_method:
        by_method[row["method"]].append(row["accuracy"])
        by_dataset_method[(row["dataset"], row["method"])].append(row["accuracy"])
        by_budget_method[(row["budget"], row["method"])].append(row["accuracy"])
        by_seed_budget_method[(row["seed"], row["budget"], row["method"])].append(row["accuracy"])

    overall = {m: {"mean_accuracy_over_budgets": _mean(v), "seed_stability_std": _std(v)} for m, v in by_method.items()}

    # candidate freeze: choose better accuracy; tie-break lower std
    v1 = overall["broad_diversity_aggregation_v1"]
    vs = overall["broad_diversity_aggregation_strong_v1"]
    if v1["mean_accuracy_over_budgets"] > vs["mean_accuracy_over_budgets"]:
        candidate = "broad_diversity_aggregation_v1"
        ablation = "broad_diversity_aggregation_strong_v1"
    elif vs["mean_accuracy_over_budgets"] > v1["mean_accuracy_over_budgets"]:
        candidate = "broad_diversity_aggregation_strong_v1"
        ablation = "broad_diversity_aggregation_v1"
    else:
        candidate = "broad_diversity_aggregation_v1" if v1["seed_stability_std"] <= vs["seed_stability_std"] else "broad_diversity_aggregation_strong_v1"
        ablation = "broad_diversity_aggregation_strong_v1" if candidate == "broad_diversity_aggregation_v1" else "broad_diversity_aggregation_v1"

    per_dataset: dict[str, dict[str, dict[str, float]]] = {}
    for (ds, m), vals in by_dataset_method.items():
        per_dataset.setdefault(ds, {})[m] = {"mean_accuracy": _mean(vals), "seed_stability_std": _std(vals)}

    budget_table: dict[str, dict[str, dict[str, float]]] = {}
    for (b, m), vals in by_budget_method.items():
        budget_table.setdefault(str(b), {})[m] = {"mean_accuracy": _mean(vals), "std_accuracy": _std(vals)}

    # aligned per-example comparisons
    aligned = defaultdict(dict)
    for r in per_example_rows:
        key = (r["dataset"], r["seed"], r["budget"], r["example_id"])
        aligned[key][r["method"]] = r
    aligned_rows = [row for row in aligned.values() if all(m in row for m in METHODS)]

    hard_slice = {
        "near_tie": {m: _slice_acc(aligned_rows, m, "near_tie") for m in METHODS},
        "disagreement": {m: _slice_acc(aligned_rows, m, "disagreement") for m in METHODS},
        "hard_case_active": {m: _slice_acc(aligned_rows, m, "hard_case_active") for m in METHODS},
    }

    # robustness: how often candidate beats sc3 by dataset/seed/budget example
    candidate_beats_sc = 0
    candidate_loses_sc = 0
    beats_by_dataset = Counter()
    loses_by_dataset = Counter()
    for row in aligned_rows:
        c_ok = bool(row[candidate]["is_correct"])
        s_ok = bool(row["self_consistency_3"]["is_correct"])
        ds = row[candidate]["dataset"]
        if c_ok and not s_ok:
            candidate_beats_sc += 1
            beats_by_dataset.update([ds])
        elif s_ok and not c_ok:
            candidate_loses_sc += 1
            loses_by_dataset.update([ds])

    total_aligned = max(1, len(aligned_rows))

    sc = overall["self_consistency_3"]["mean_accuracy_over_budgets"]
    baseline = overall["adaptive_min_expand_1"]["mean_accuracy_over_budgets"]
    hybrid = overall["selective_sc_hybrid_v1"]["mean_accuracy_over_budgets"]
    cand = overall[candidate]["mean_accuracy_over_budgets"]

    aggregate_summary = {
        "overall_method_summary": overall,
        "hard_slice_summary": hard_slice,
        "gap_to_self_consistency_3": {
            "adaptive_min_expand_1": float(sc - baseline),
            "selective_sc_hybrid_v1": float(sc - hybrid),
            candidate: float(sc - cand),
        },
        "gap_reduction": {
            "vs_adaptive_min_expand_1": float(cand - baseline),
            "vs_selective_sc_hybrid_v1": float(cand - hybrid),
            "material_narrowing_flag": bool(((sc - hybrid) - (sc - cand)) >= 0.02),
        },
        "robustness": {
            "candidate_beats_sc_count": int(candidate_beats_sc),
            "candidate_loses_sc_count": int(candidate_loses_sc),
            "candidate_beats_sc_rate": float(candidate_beats_sc / total_aligned),
            "candidate_loses_sc_rate": float(candidate_loses_sc / total_aligned),
            "beats_by_dataset": dict(beats_by_dataset),
            "loses_by_dataset": dict(loses_by_dataset),
        },
        "conclusion": (
            "broad diversity candidate remains a serious broad competitor under stricter pass"
            if cand >= sc - 0.01
            else "broad diversity candidate weakens under stricter pass and is not yet robustly broad"
        ),
    }

    # budget stability / variance indicators
    budget_stability = {
        "per_budget_method": budget_table,
        "seed_budget_variance": {
            f"{seed}|{budget}": {
                m: _mean(vals)
                for (s2, b2, m), vals in by_seed_budget_method.items()
                if s2 == seed and b2 == budget
            }
            for seed in seeds
            for budget in budgets
        },
    }

    # Diversity mechanism realism audit
    cand_rows = [r for r in per_example_rows if r["method"] == candidate]
    diversity_audit = {
        "candidate": candidate,
        "answer_group_concentration": {
            "mean_group_support_fraction": _mean([r["group_support_fraction"] for r in cand_rows]),
            "mean_unique_answer_groups_seen": _mean([float(r["unique_answer_groups_seen"]) for r in cand_rows]),
            "mean_answer_support_entropy": _mean([r["answer_support_entropy"] for r in cand_rows]),
        },
        "duplicate_suppression_behavior": {
            "mean_duplicate_penalty_applied_rate": _mean([r["duplicate_penalty_applied_rate"] for r in cand_rows]),
            "mean_diversity_bonus_on_expand": _mean([r["mean_diversity_bonus_on_expand"] for r in cand_rows]),
        },
        "commit_delay_behavior": {
            "mean_forced_explore_rate": _mean([r["forced_explore_rate"] for r in cand_rows]),
            "aggregation_used_rate": _mean([1.0 if r["aggregation_used"] else 0.0 for r in cand_rows]),
        },
        "diversity_failure_cases": {
            "low_diversity_count": int(sum(1 for r in cand_rows if r["unique_answer_groups_seen"] <= 1)),
            "weak_support_concentration_count": int(sum(1 for r in cand_rows if r["group_support_fraction"] < 0.45)),
        },
    }

    # Residual-loss taxonomy where SC still beats candidate
    residual = Counter()
    for row in aligned_rows:
        c = row[candidate]
        s = row["self_consistency_3"]
        if (not c["is_correct"]) and s["is_correct"]:
            if int(c["unique_answer_groups_seen"]) <= 1:
                residual.update(["insufficient_diversity_realized"])
            elif float(c["group_support_fraction"]) < 0.45:
                residual.update(["aggregation_concentration_failure"])
            elif float(c["answer_support_entropy"]) > 0.2:
                residual.update(["value_ranking_error_despite_diversity"])
            else:
                residual.update(["answer_normalization_or_selection_error"])

    residual_tax = {
        "candidate": candidate,
        "residual_loss_counts": dict(residual),
        "residual_loss_total": int(sum(residual.values())),
    }

    candidate_selection = {
        "main_candidate": candidate,
        "ablation_variant": ablation,
        "selection_rule": "higher mean_accuracy_over_budgets, tie-break lower seed_stability_std",
        "candidate_metrics": overall[candidate],
        "ablation_metrics": overall[ablation],
    }

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_broad_diversity_aggregation_confirmation_20260418.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": METHODS,
    }

    methods_compared = {"methods": METHODS, "main_candidate": candidate, "ablation": ablation}
    datasets_compared = {"datasets": datasets, "seeds": seeds, "budgets": budgets, "subset_size": args.subset_size}

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "methods_compared.json").write_text(json.dumps(methods_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "datasets_compared.json").write_text(json.dumps(datasets_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "candidate_selection_summary.json").write_text(json.dumps(candidate_selection, indent=2) + "\n", encoding="utf-8")
    (out_dir / "aggregate_comparison_summary.json").write_text(json.dumps(aggregate_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_dataset_tables.json").write_text(json.dumps({"per_dataset": per_dataset, "budget_table": budget_table}, indent=2) + "\n", encoding="utf-8")
    (out_dir / "budget_stability_summary.json").write_text(json.dumps(budget_stability, indent=2) + "\n", encoding="utf-8")
    (out_dir / "diversity_mechanism_audit.json").write_text(json.dumps(diversity_audit, indent=2) + "\n", encoding="utf-8")
    (out_dir / "residual_loss_taxonomy.json").write_text(json.dumps(residual_tax, indent=2) + "\n", encoding="utf-8")

    commands_md = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Command run",
            f"- python scripts/run_broad_diversity_aggregation_confirmation_20260418.py --datasets {','.join(datasets)} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
            "",
            "## Assumptions",
            "- Stricter but bounded simulator-mode confirmation (larger subset, more seeds, expanded budgets).",
            "- Same canonical fixed-budget branch-allocation framing retained.",
            "",
            "## Caveats",
            "- Still simulator-mode; additional real-model confirmation is still required for final paper claims.",
            "- Hard-slice definitions reuse selective-hybrid markers for cross-method comparability.",
        ]
    )
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_md + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "main_candidate": candidate}, indent=2))


if __name__ == "__main__":
    main()
