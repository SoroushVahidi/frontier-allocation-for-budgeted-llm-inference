#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

BASE = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1"
BEST = "broad_diversity_aggregation_strong_v1_incumbent_challenger_metalevel_v2"


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _safe_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _failure_group(row: dict[str, Any]) -> str:
    if row["is_correct"]:
        return "correct"
    m = row.get("metadata") or {}
    if row.get("prediction") is None:
        return "incomplete_or_non_terminal"
    if row.get("budget_exhausted") or (not bool(m.get("commit_triggered", False)) and int(row.get("actions_used", 0)) >= int(row.get("budget", 0)) - 1):
        return "wrong_commit_timing"
    if _safe_float(m.get("answer_group_margin", 0.0)) <= 0.20:
        return "ambiguity_near_tie"
    return "other"


def _selector_refined_v2() -> dict[str, Any]:
    return {
        "challenger_upside_commit_max": 0.15,
        "metalevel_delta_margin": 0.00,
        "near_tie_commit_margin_extra": 0.00,
        "force_extra_explore_on_near_tie": True,
        "near_tie_force_upside_frac_threshold": 0.60,
        "challenger_overthrow_weight": 0.90,
        "challenger_correlation_penalty": 0.30,
        "challenger_repeat_failure_penalty": 0.14,
        "challenger_min_relative_upside": 0.02,
        "challenger_low_margin_penalty": 0.08,
    }


def _variants() -> dict[str, dict[str, Any]]:
    base = _selector_refined_v2()
    return {
        "metalevel_v2_selector_refined_v2": {**base},
        "metalevel_v2_selector_refined_v2_commit_tuned_v1": {
            **base,
            "stop_continue_value_margin": 0.01,
            "remaining_budget_commit_bias": 0.04,
            "late_stage_commit_bonus": 0.02,
            "near_tie_commit_band": 0.04,
            "continue_requires_min_best_value": 0.04,
        },
        "metalevel_v2_selector_refined_v2_commit_tuned_v2": {
            **base,
            "stop_continue_value_margin": 0.01,
            "remaining_budget_commit_bias": 0.05,
            "late_stage_commit_bonus": 0.03,
            "near_tie_commit_band": 0.06,
            "continue_requires_min_best_value": 0.05,
            "force_extra_explore_on_near_tie": False,
        },
    }


def _apply_variant(ctrl: Any, params: dict[str, Any]) -> None:
    for k, v in params.items():
        setattr(ctrl, k, v)


def _harmed_subtype(row: dict[str, Any]) -> str:
    m = row.get("metadata") or {}
    if int(m.get("wrong_challenger_chosen_count", 0)) > 0:
        return "residual_wrong_challenger"
    if int(m.get("near_tie_commit_blocked_count", 0)) > 0:
        return "commit_blocked_by_near_tie_rule"
    if int(m.get("late_commit_after_selector_count", 0)) > 0:
        return "late_commit_after_improved_challenger_selection"
    if int(m.get("false_non_stop_count", 0)) > 0:
        return "false_non_stop"
    return "other"


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded matched commit-interaction refinement comparison")
    p.add_argument("--datasets", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_commit_interaction_refinement_bounded_eval_20260419")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)
    variant_defs = _variants()

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    rng_master = random.Random(20260419)

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                rng = random.Random(rng_master.randint(0, 10**9))
                factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
                base_specs = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                )

                method_ctrls: dict[str, Any] = {"baseline": base_specs[BASE]}
                for name, params in variant_defs.items():
                    rng_v = random.Random(rng_master.randint(0, 10**9))
                    factory_v = generator_factory_for_mode(False, rng_v, "gpt-4.1-mini", 0.2, 180, 45)
                    specs_v = build_frontier_strategies(
                        factory_v,
                        budget,
                        adaptive_grid,
                        rng_v,
                        use_openai_api=False,
                        include_selective_sc_hybrid_methods=True,
                        include_broad_diversity_aggregation_methods=True,
                    )
                    ctrl = specs_v[BEST]
                    _apply_variant(ctrl, params)
                    method_ctrls[name] = ctrl

                for ex in examples:
                    for method_name, ctrl in method_ctrls.items():
                        r = ctrl.run(ex.question, ex.answer)
                        row = {
                            "dataset": dataset,
                            "seed": int(seed),
                            "budget": int(budget),
                            "example_id": ex.example_id,
                            "method": method_name,
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "actions_used": int(r.actions_used),
                            "expansions": int(r.expansions),
                            "verifications": int(r.verifications),
                            "budget_exhausted": bool(r.budget_exhausted),
                            "metadata": r.metadata,
                            "variant_params": variant_defs.get(method_name, {}),
                        }
                        row["failure_group"] = _failure_group(row)
                        rows.append(row)

    (out_dir / "per_example_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[str(r["method"])].append(r)

    methods = ["baseline", *variant_defs.keys()]
    metrics: dict[str, dict[str, Any]] = {}
    for m in methods:
        mr = by_method.get(m, [])
        n = max(1, len(mr))
        action_trace = [a for r in mr for a in ((r.get("metadata") or {}).get("action_trace") or [])]
        action_counts = Counter(str(a.get("action", "")) for a in action_trace)
        metrics[m] = {
            "n_examples": len(mr),
            "accuracy": sum(int(r["is_correct"]) for r in mr) / n,
            "wrong_commit_timing_count": sum(1 for r in mr if r.get("failure_group") == "wrong_commit_timing"),
            "wrong_challenger_chosen_count": int(sum(int((r.get("metadata") or {}).get("wrong_challenger_chosen_count", 0)) for r in mr)),
            "false_non_stop_count": int(sum(int((r.get("metadata") or {}).get("false_non_stop_count", 0)) for r in mr)),
            "commit_vs_expand_counts": {
                "commit": int(sum(int((r.get("metadata") or {}).get("commit_action_count", 0)) for r in mr)),
                "expand": int(action_counts.get("expand", 0)),
            },
            "late_stage_commit_rate": float(sum(_safe_float((r.get("metadata") or {}).get("late_stage_commit_rate", 0.0)) for r in mr) / n),
            "near_tie_continuation_rate": float(sum(_safe_float((r.get("metadata") or {}).get("near_tie_continuation_rate", 0.0)) for r in mr) / n),
            "mean_best_continue_value_when_continue": float(
                sum(_safe_float((r.get("metadata") or {}).get("mean_best_continue_value_when_continue", 0.0)) for r in mr) / n
            ),
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        aligned[(str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))][str(r["method"])] = r

    cmp: dict[str, dict[str, Any]] = {}
    for m in variant_defs.keys():
        improved = harmed = 0
        harmed_subtypes = Counter()
        baseline_commit_refined_continue_values: list[float] = []
        for pair in aligned.values():
            if "baseline" not in pair or m not in pair:
                continue
            b = pair["baseline"]
            c = pair[m]
            if (not b["is_correct"]) and c["is_correct"]:
                improved += 1
            elif b["is_correct"] and (not c["is_correct"]):
                harmed += 1
                harmed_subtypes[_harmed_subtype(c)] += 1
            baseline_commit_triggered = bool((b.get("metadata") or {}).get("commit_triggered", False))
            refined_commit_triggered = bool((c.get("metadata") or {}).get("commit_triggered", False))
            if baseline_commit_triggered and (not refined_commit_triggered):
                baseline_commit_refined_continue_values.append(
                    _safe_float((c.get("metadata") or {}).get("mean_best_continue_value_when_continue", 0.0))
                )

        cmp[m] = {
            "improved_count": int(improved),
            "harmed_count": int(harmed),
            "harmed_subtype_counts": dict(harmed_subtypes),
            "delta_accuracy_vs_baseline": float(metrics[m]["accuracy"] - metrics["baseline"]["accuracy"]),
            "delta_wrong_commit_timing_vs_baseline": int(metrics[m]["wrong_commit_timing_count"] - metrics["baseline"]["wrong_commit_timing_count"]),
            "delta_wrong_challenger_count_vs_baseline": int(
                metrics[m]["wrong_challenger_chosen_count"] - metrics["baseline"]["wrong_challenger_chosen_count"]
            ),
            "mean_best_continue_value_on_baseline_commit_refined_continue": float(
                sum(baseline_commit_refined_continue_values) / max(1, len(baseline_commit_refined_continue_values))
            ),
            "n_baseline_commit_refined_continue": int(len(baseline_commit_refined_continue_values)),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_type": "bounded_commit_interaction_refinement_comparison",
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": int(args.subset_size),
        "variant_params": variant_defs,
        "metrics": metrics,
        "comparison_vs_baseline": cmp,
        "notes": [
            "Small matched comparison only; no broad sweep.",
            "Focus is commit-side interaction after improved selector inside same metalevel ICC family.",
        ],
    }

    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    diagnostics = {
        "generated_at": payload["generated_at"],
        "methods": {
            m: {
                "false_non_stop_count": metrics[m]["false_non_stop_count"],
                "wrong_commit_timing_count": metrics[m]["wrong_commit_timing_count"],
                "wrong_challenger_chosen_count": metrics[m]["wrong_challenger_chosen_count"],
                "commit_vs_expand_counts": metrics[m]["commit_vs_expand_counts"],
                "late_stage_commit_rate": metrics[m]["late_stage_commit_rate"],
                "near_tie_continuation_rate": metrics[m]["near_tie_continuation_rate"],
                "mean_best_continue_value_when_continue": metrics[m]["mean_best_continue_value_when_continue"],
            }
            for m in methods
        },
        "harmed_case_subtypes_vs_baseline": {
            m: cmp[m]["harmed_subtype_counts"] for m in variant_defs.keys()
        },
    }
    (out_dir / "commit_side_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
