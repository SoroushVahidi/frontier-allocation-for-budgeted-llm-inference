#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

TARGET_METHODS = [
    "self_consistency_3",
    "adaptive_min_expand_1",
    "intermediate_trap_aware_near_tie_v1",
    "selective_sc_hybrid_v1",
]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _error_tag(pred: Any, gold: str) -> str:
    if pred is None:
        return "no_answer"
    p = str(pred).strip()
    if not p:
        return "empty_answer"
    try:
        pv = float(p)
        gv = float(gold)
        if abs(pv - gv) == 1:
            return "off_by_one"
        return "numeric_mismatch"
    except ValueError:
        return "format_or_parse"


def main() -> None:
    p = argparse.ArgumentParser(description="Broad selective self-consistency hybrid evaluation pass")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/self_consistency_hybrid_broad_eval_20260418")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

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
                )
                strategies = {k: v for k, v in strategies.items() if k in TARGET_METHODS}
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
                            "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                            "n_eval_examples": int(m["n_examples"]),
                        }
                    )

                for r in rows:
                    if r["strategy"] not in TARGET_METHODS:
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
                            "prediction": meta.get("final_prediction") if isinstance(meta.get("final_prediction"), str) else None,
                            "actions_used": int(r["actions_used"]),
                            "hard_case_active": bool(meta.get("hard_case_active", False)),
                            "consensus_override": bool(meta.get("consensus_override", False)),
                            "near_tie": bool(meta.get("near_tie", False)),
                            "continuation_completion_disagree": bool(meta.get("continuation_completion_disagree", False)),
                            "low_top_completion": bool(meta.get("low_top_completion", False)),
                        }
                    )

    # Build index by (dataset, seed, budget, example)
    key_rows: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in per_example_rows:
        key = (row["dataset"], int(row["seed"]), int(row["budget"]), row["example_id"])
        key_rows[key][row["method"]] = row

    gap_records = []
    hybrid_activation = []
    failure_counter = Counter()
    remaining_gap_counter = Counter()

    for key, mrows in key_rows.items():
        if not all(m in mrows for m in TARGET_METHODS):
            continue
        sc = mrows["self_consistency_3"]
        canon = mrows["adaptive_min_expand_1"]
        inter = mrows["intermediate_trap_aware_near_tie_v1"]
        hybrid = mrows["selective_sc_hybrid_v1"]

        slice_near = bool(hybrid["near_tie"])
        slice_disagree = bool(hybrid["continuation_completion_disagree"])
        slice_hard = bool(hybrid["hard_case_active"])

        gap_records.append(
            {
                "dataset": key[0],
                "seed": key[1],
                "budget": key[2],
                "example_id": key[3],
                "slice_near_tie": slice_near,
                "slice_disagreement": slice_disagree,
                "slice_hard": slice_hard,
                "sc_correct": sc["is_correct"],
                "canonical_correct": canon["is_correct"],
                "intermediate_correct": inter["is_correct"],
                "hybrid_correct": hybrid["is_correct"],
            }
        )

        hybrid_activation.append(
            {
                "dataset": key[0],
                "seed": key[1],
                "budget": key[2],
                "example_id": key[3],
                "hard_case_active": slice_hard,
                "consensus_override": bool(hybrid["consensus_override"]),
                "near_tie": slice_near,
                "continuation_completion_disagree": slice_disagree,
                "low_top_completion": bool(hybrid["low_top_completion"]),
                "wasted_on_easy": bool(slice_hard and sc["is_correct"] and hybrid["is_correct"]),
                "missed_hard_case": bool((not slice_hard) and sc["is_correct"] and (not hybrid["is_correct"])),
            }
        )

        if (not hybrid["is_correct"]) and sc["is_correct"]:
            reason = "wrong_activation_region"
            if not slice_hard:
                reason = "over_conservative_gating"
            elif not hybrid["consensus_override"]:
                reason = "insufficient_diversity_or_aggregation"
            remaining_gap_counter.update([reason])

    # Aggregate metrics
    by_method_budget = defaultdict(list)
    by_method_dataset = defaultdict(list)
    by_method = defaultdict(list)
    for row in per_seed_method:
        by_method_budget[(row["method"], row["budget"])].append(row["accuracy"])
        by_method_dataset[(row["method"], row["dataset"])].append(row["accuracy"])
        by_method[row["method"]].append(row["accuracy"])

    overall = {
        str(method): {
            "mean_accuracy_over_budgets": float(sum(vals) / len(vals)),
            "seed_stability_std": float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0,
        }
        for method, vals in by_method.items()
    }

    per_dataset = {}
    for (method, dataset), vals in by_method_dataset.items():
        per_dataset.setdefault(dataset, {})[method] = {
            "mean_accuracy": float(sum(vals) / len(vals)),
            "seed_stability_std": float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0,
        }

    budget_table = {}
    for (method, budget), vals in by_method_budget.items():
        budget_table.setdefault(str(budget), {})[method] = {
            "mean_accuracy": float(sum(vals) / len(vals)),
            "std_accuracy": float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0,
        }

    def _slice_mean(method_key: str, slice_key: str) -> float:
        vals = [int(r[f"{method_key}_correct"]) for r in gap_records if r[slice_key]]
        if not vals:
            return 0.0
        return float(sum(vals) / len(vals))

    hard_slice = {
        "near_tie": {m: _slice_mean(m, "slice_near_tie") for m in ["sc", "canonical", "intermediate", "hybrid"]},
        "disagreement": {m: _slice_mean(m, "slice_disagreement") for m in ["sc", "canonical", "intermediate", "hybrid"]},
        "hard": {m: _slice_mean(m, "slice_hard") for m in ["sc", "canonical", "intermediate", "hybrid"]},
    }

    sc_gap = overall["self_consistency_3"]["mean_accuracy_over_budgets"] - overall["selective_sc_hybrid_v1"]["mean_accuracy_over_budgets"]
    sc_gap_prev = overall["self_consistency_3"]["mean_accuracy_over_budgets"] - overall["adaptive_min_expand_1"]["mean_accuracy_over_budgets"]
    gap_reduction = sc_gap_prev - sc_gap

    budget_gap_reduction = {
        "overall": {
            "gap_sc_vs_canonical": float(sc_gap_prev),
            "gap_sc_vs_hybrid": float(sc_gap),
            "gap_reduction": float(gap_reduction),
            "material_narrowing": bool(gap_reduction >= 0.02),
        },
        "by_budget": {},
    }
    for budget in budgets:
        b = str(budget)
        sc_vals = by_method_budget.get(("self_consistency_3", budget), [])
        canon_vals = by_method_budget.get(("adaptive_min_expand_1", budget), [])
        hyb_vals = by_method_budget.get(("selective_sc_hybrid_v1", budget), [])
        if not (sc_vals and canon_vals and hyb_vals):
            continue
        sc_b = float(sum(sc_vals) / len(sc_vals))
        canon_b = float(sum(canon_vals) / len(canon_vals))
        hyb_b = float(sum(hyb_vals) / len(hyb_vals))
        budget_gap_reduction["by_budget"][b] = {
            "gap_sc_vs_canonical": float(sc_b - canon_b),
            "gap_sc_vs_hybrid": float(sc_b - hyb_b),
            "gap_reduction": float((sc_b - canon_b) - (sc_b - hyb_b)),
        }

    act_n = max(1, len(hybrid_activation))
    activation_summary = {
        "n_examples": len(hybrid_activation),
        "hard_case_activation_rate": float(sum(int(r["hard_case_active"]) for r in hybrid_activation) / act_n),
        "consensus_override_rate": float(sum(int(r["consensus_override"]) for r in hybrid_activation) / act_n),
        "near_tie_activation_rate": float(sum(int(r["near_tie"]) for r in hybrid_activation) / act_n),
        "disagreement_activation_rate": float(sum(int(r["continuation_completion_disagree"]) for r in hybrid_activation) / act_n),
        "wasted_on_easy_rate": float(sum(int(r["wasted_on_easy"]) for r in hybrid_activation) / act_n),
        "missed_hard_case_rate": float(sum(int(r["missed_hard_case"]) for r in hybrid_activation) / act_n),
    }

    failure_taxonomy = {
        "where_hybrid_beats_canonical": {
            "count": int(sum(1 for r in gap_records if r["hybrid_correct"] and not r["canonical_correct"])),
            "rate": float(sum(1 for r in gap_records if r["hybrid_correct"] and not r["canonical_correct"]) / max(1, len(gap_records))),
        },
        "where_hybrid_loses_to_sc": {
            "count": int(sum(1 for r in gap_records if (not r["hybrid_correct"]) and r["sc_correct"])),
            "rate": float(sum(1 for r in gap_records if (not r["hybrid_correct"]) and r["sc_correct"]) / max(1, len(gap_records))),
        },
        "remaining_gap_reason_counts": dict(remaining_gap_counter),
        "classification": {
            "premature_commitment": int(remaining_gap_counter.get("over_conservative_gating", 0)),
            "insufficient_diversity": int(remaining_gap_counter.get("insufficient_diversity_or_aggregation", 0)),
            "weak_answer_aggregation": int(remaining_gap_counter.get("insufficient_diversity_or_aggregation", 0)),
            "wrong_activation_region": int(remaining_gap_counter.get("wrong_activation_region", 0)),
            "over_conservative_gating": int(remaining_gap_counter.get("over_conservative_gating", 0)),
            "cost_budget_inefficiency": int(sum(1 for r in per_seed_method if r["method"] == "selective_sc_hybrid_v1" and _as_float(r["avg_actions"]) > 0.95 * _as_float(r["budget"]))),
        },
    }

    aggregate_summary = {
        "overall_method_summary": overall,
        "hard_slice_summary": hard_slice,
        "gap_to_self_consistency_3": {
            "vs_canonical": float(sc_gap_prev),
            "vs_hybrid": float(sc_gap),
            "gap_reduction_vs_canonical": float(gap_reduction),
            "material_narrowing": bool(gap_reduction >= 0.02),
        },
        "conclusion": (
            "hybrid materially narrows the broad gap" if gap_reduction >= 0.02 else "hybrid does not materially narrow the broad gap"
        ),
    }

    methods_compared = {
        "methods": TARGET_METHODS,
        "optional_context_methods_not_included": ["multistep_k3_current", "best_bounded_learned_branch_score_current"],
        "note": "comparison executed in matched simulator setting using frontier strategy controllers",
    }

    datasets_compared = {
        "datasets": datasets,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "matched_setting": True,
    }

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_self_consistency_hybrid_broad_eval_20260418.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "methods": TARGET_METHODS,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "methods_compared.json").write_text(json.dumps(methods_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "datasets_compared.json").write_text(json.dumps(datasets_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "aggregate_comparison_summary.json").write_text(json.dumps(aggregate_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_dataset_tables.json").write_text(json.dumps({"per_dataset": per_dataset, "budget_table": budget_table}, indent=2) + "\n", encoding="utf-8")
    (out_dir / "budget_gap_reduction.json").write_text(json.dumps(budget_gap_reduction, indent=2) + "\n", encoding="utf-8")
    (out_dir / "activation_behavior_summary.json").write_text(json.dumps(activation_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "failure_gap_taxonomy.json").write_text(json.dumps(failure_taxonomy, indent=2) + "\n", encoding="utf-8")

    commands_md = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Command run",
            f"- python scripts/run_self_consistency_hybrid_broad_eval_20260418.py --datasets {','.join(datasets)} --subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}",
            "",
            "## Assumptions",
            "- Evaluations run in simulator-mode using in-repo frontier controllers for matched comparisons.",
            "- Hybrid and intermediate methods are bounded controller variants added to the same evaluation harness.",
            "- Hard/near-tie slices are defined by hybrid activation signals in matched per-example contexts.",
            "",
            "## Caveats",
            "- This is a light broad pass (pilot subsets), not final paper-scale benchmark evidence.",
            "- multistep_k3_current and strict learned branch-score methods are reported as context methods but not executed in this harness.",
        ]
    )
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_md + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
