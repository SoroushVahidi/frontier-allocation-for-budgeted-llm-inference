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


def _load_bundle(bundle_name: str) -> list[str]:
    payload = json.loads((REPO_ROOT / "configs/dataset_experiment_readiness_bundles.json").read_text(encoding="utf-8"))
    return [str(x) for x in (((payload.get("bundles") or {}).get(bundle_name) or {}).get("datasets") or [])]


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


def _variants() -> dict[str, dict[str, Any]]:
    common = {
        "challenger_upside_commit_max": 0.15,
        "metalevel_delta_margin": 0.00,
        "near_tie_commit_margin_extra": 0.00,
        "force_extra_explore_on_near_tie": True,
        "near_tie_force_upside_frac_threshold": 0.60,
    }
    return {
        "metalevel_v2_best": {
            **common,
            "challenger_overthrow_weight": 0.55,
            "challenger_correlation_penalty": 0.18,
            "challenger_repeat_failure_penalty": 0.08,
            "challenger_min_relative_upside": 0.01,
            "challenger_low_margin_penalty": 0.06,
        },
        "metalevel_v2_refined_overthrow_v1": {
            **common,
            "challenger_overthrow_weight": 0.75,
            "challenger_correlation_penalty": 0.22,
            "challenger_repeat_failure_penalty": 0.10,
            "challenger_min_relative_upside": 0.015,
            "challenger_low_margin_penalty": 0.06,
        },
        "metalevel_v2_refined_overthrow_v2": {
            **common,
            "challenger_overthrow_weight": 0.90,
            "challenger_correlation_penalty": 0.30,
            "challenger_repeat_failure_penalty": 0.14,
            "challenger_min_relative_upside": 0.02,
            "challenger_low_margin_penalty": 0.08,
        },
    }


def _apply_variant(ctrl: Any, params: dict[str, Any]) -> None:
    for k, v in params.items():
        setattr(ctrl, k, v)


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded matched selector refinement comparison")
    p.add_argument("--bundle", default="exact_answer_math_expansion")
    p.add_argument("--datasets", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_selector_refinement_bounded_eval_20260419")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets.strip() else _load_bundle(args.bundle)
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
                base_ctrl = base_specs[BASE]
                best_ctrl = base_specs[BEST]

                method_ctrls: dict[str, Any] = {"baseline": base_ctrl}
                for name, params in variant_defs.items():
                    # Rebuild candidate controller each variant to avoid shared mutable state.
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
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
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
        challenger_counts = [int((r.get("metadata") or {}).get("wrong_challenger_chosen_count", 0)) for r in mr]
        challenger_events = [int((r.get("metadata") or {}).get("challenger_selection_event_count", 0)) for r in mr]
        overtook = [
            int(((r.get("metadata") or {}).get("challenger_outcome_counts") or {}).get("later_overtook_incumbent", 0))
            for r in mr
        ]
        dominated = [
            int(((r.get("metadata") or {}).get("challenger_outcome_counts") or {}).get("dominated_ex_post_by_other_challenger", 0))
            for r in mr
        ]
        metrics[m] = {
            "n_examples": len(mr),
            "accuracy": sum(int(r["is_correct"]) for r in mr) / n,
            "wrong_commit_timing_count": sum(1 for r in mr if r.get("failure_group") == "wrong_commit_timing"),
            "commit_triggered_count": sum(int(bool((r.get("metadata") or {}).get("commit_triggered", False))) for r in mr),
            "expand_action_count": int(action_counts.get("expand", 0)),
            "verify_action_count": int(action_counts.get("verify", 0)),
            "avg_actions": sum(float(r.get("actions_used", 0)) for r in mr) / n,
            "wrong_challenger_chosen_count": int(sum(challenger_counts)),
            "challenger_overtook_rate": float(sum(overtook) / max(1, sum(challenger_events))),
            "challenger_dominated_rate": float(sum(dominated) / max(1, sum(challenger_events))),
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        aligned[(str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))][str(r["method"])] = r

    cmp: dict[str, dict[str, Any]] = {}
    for m in variant_defs.keys():
        improved = 0
        harmed = 0
        wrong_challenger_harmed = 0
        for pair in aligned.values():
            if "baseline" not in pair or m not in pair:
                continue
            b = pair["baseline"]
            c = pair[m]
            if (not b["is_correct"]) and c["is_correct"]:
                improved += 1
            elif b["is_correct"] and (not c["is_correct"]):
                harmed += 1
                if int((c.get("metadata") or {}).get("wrong_challenger_chosen_count", 0)) > 0:
                    wrong_challenger_harmed += 1
        cmp[m] = {
            "improved_count": int(improved),
            "harmed_count": int(harmed),
            "wrong_challenger_harmed_count": int(wrong_challenger_harmed),
            "delta_accuracy_vs_baseline": float(metrics[m]["accuracy"] - metrics["baseline"]["accuracy"]),
            "delta_wrong_commit_timing_vs_baseline": int(metrics[m]["wrong_commit_timing_count"] - metrics["baseline"]["wrong_commit_timing_count"]),
            "delta_wrong_challenger_count_vs_baseline": int(metrics[m]["wrong_challenger_chosen_count"] - metrics["baseline"]["wrong_challenger_chosen_count"]),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_type": "bounded_selector_refinement_comparison",
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": int(args.subset_size),
        "variant_params": variant_defs,
        "metrics": metrics,
        "comparison_vs_baseline": cmp,
        "notes": [
            "Small matched comparison only; no broad sweep.",
            "Focus is wrong-challenger selection inside same metalevel ICC family.",
        ],
    }

    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
