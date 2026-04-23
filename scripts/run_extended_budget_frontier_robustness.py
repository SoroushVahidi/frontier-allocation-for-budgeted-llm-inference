#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
import importlib.util


DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
SEEDS = [11, 23]
BUDGETS = [10, 12, 14]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]



def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_extended_budget", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()

METHOD_SPECS: list[tuple[str, str]] = [
    (
        "strict_gate1_cap_k6",
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1",
    ),
    (
        "strict_f2",
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1",
    ),
    (
        "strict_f3",
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1",
    ),
    ("external_s1_budget_forcing", "external_s1_budget_forcing"),
    ("external_tale_prompt_budgeting", "external_tale_prompt_budgeting"),
    ("external_l1_max", "external_l1_max"),
    ("external_l1_exact", "external_l1_exact"),
]


def _parse_int_list(raw: str) -> list[int]:
    return sorted({int(x.strip()) for x in raw.split(",") if x.strip()})


def _runtime_method(name: str) -> str:
    x = name
    repair_suffix = "__deterministic_output_layer_repair_v1"
    if x.endswith(repair_suffix):
        x = x[: -len(repair_suffix)]
    if x.endswith("_hard_max_family_expansions_cap_k6_v1"):
        x = x + "_fixed_k6_control"
    return x


def _stable_seed(*parts: Any) -> int:
    text = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty csv: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _method_class(method: str) -> str:
    if method.startswith("external_"):
        return "near_direct_external"
    return "inhouse"


def _run_method(
    method_public: str,
    method_runtime: str,
    dataset: str,
    seed: int,
    budget: int,
    example: Any,
) -> dict[str, Any]:
    run_seed = _stable_seed("extended_budget_robustness", method_public, dataset, seed, budget, example.example_id)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    strategies = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    if method_runtime not in strategies:
        raise KeyError(f"{method_public} unavailable (runtime key: {method_runtime})")

    result = strategies[method_runtime].run(example.question, example.answer)
    final_nodes = []
    for _, branch in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        final_nodes.append(observed._snapshot(branch))

    repair = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    answer = canonicalize_answer(repair.get("surfaced_final_answer_raw"), dataset=dataset)
    gold = canonicalize_answer(str(example.answer), dataset=dataset)

    gold_in_tree = bool(gold is not None and any(n.get("predicted_answer_normalized") == gold for n in final_nodes))
    output_mismatch = bool(
        gold_in_tree
        and (repair.get("chosen_final_node_answer_canonical") == gold)
        and (answer != gold)
    )
    extraction_mismatch = bool(
        repair.get("chosen_final_node_answer_canonical") != repair.get("extracted_final_answer_canonical")
        or repair.get("extracted_final_answer_canonical") != repair.get("surfaced_final_answer_canonical")
    )
    is_correct = bool(answer == gold and answer is not None)

    if not gold_in_tree:
        failure_type = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure_type = "output_layer_mismatch"
    elif is_correct:
        failure_type = "correct"
    else:
        failure_type = "present_not_selected"

    md = result.metadata or {}
    repeated = bool(
        float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0
        or int(md.get("repeated_same_family_expansion_count", 0)) > 0
    )

    return {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": str(example.example_id),
        "method": method_public,
        "method_class": _method_class(method_public),
        "is_correct": int(is_correct),
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "failure_type": failure_type,
        "absent_from_tree": int(failure_type == "absent_from_tree"),
        "present_not_selected": int(failure_type == "present_not_selected"),
        "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
        "gold_in_tree": int(gold_in_tree),
        "repeated_same_family_present": int(repeated),
    }


def _aggregate(rows: list[dict[str, Any]], group_keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        grouped[key].append(row)

    out: list[dict[str, Any]] = []
    for key, vals in sorted(grouped.items()):
        method = str(vals[0]["method"]) if "method" in vals[0] else ""
        record: dict[str, Any] = {k: v for k, v in zip(group_keys, key)}
        record.update(
            {
                "method_class": _method_class(method) if method else "",
                "n_cases": len(vals),
                "mean_accuracy": _mean([float(v["is_correct"]) for v in vals]),
                "avg_actions": _mean([float(v["actions"]) for v in vals]),
                "avg_expansions": _mean([float(v["expansions"]) for v in vals]),
                "avg_verifications": _mean([float(v["verifications"]) for v in vals]),
                "absent_from_tree_rate": _mean([float(v["absent_from_tree"]) for v in vals]),
                "present_not_selected_rate": _mean([float(v["present_not_selected"]) for v in vals]),
                "output_layer_mismatch_rate": _mean([float(v["output_layer_mismatch"]) for v in vals]),
                "repeated_same_family_case_rate": _mean([float(v["repeated_same_family_present"]) for v in vals]),
            }
        )
        out.append(record)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run extended-budget (10/12/14) manuscript-surface robustness bundle.")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--budgets", default=",".join(str(x) for x in BUDGETS))
    parser.add_argument("--seeds", default=",".join(str(x) for x in SEEDS))
    args = parser.parse_args()

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)
    out_dir = REPO_ROOT / "outputs" / f"extended_budget_frontier_{args.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_specs = [(public, _runtime_method(full)) for public, full in METHOD_SPECS]
    probe_rng = random.Random(0)
    probe = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=probe_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        10,
        ADAPTIVE_GRID,
        probe_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    excluded_methods = []
    runnable_specs = []
    for public, runtime in runtime_specs:
        if runtime in probe:
            runnable_specs.append((public, runtime))
        else:
            excluded_methods.append({"method": public, "reason": "runtime_key_not_available", "runtime_key": runtime})

    per_case_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in budgets:
                for example in examples:
                    for method_public, runtime in runnable_specs:
                        per_case_rows.append(
                            _run_method(
                                method_public=method_public,
                                method_runtime=runtime,
                                dataset=dataset,
                                seed=seed,
                                budget=budget,
                                example=example,
                            )
                        )

    comparison_table = _aggregate(per_case_rows, ["method"])
    comparison_table.sort(key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))

    per_budget_summary = _aggregate(per_case_rows, ["budget", "method"])
    per_budget_summary.sort(key=lambda r: (int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"])))

    per_dataset_summary = _aggregate(per_case_rows, ["dataset", "budget", "method"])
    per_dataset_summary.sort(
        key=lambda r: (str(r["dataset"]), int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"]))
    )

    per_seed_summary = _aggregate(per_case_rows, ["seed", "budget", "method"])
    per_seed_summary.sort(key=lambda r: (int(r["seed"]), int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"])))

    frontier = [
        {
            "budget": int(r["budget"]),
            "method": r["method"],
            "method_class": r["method_class"],
            "mean_accuracy": r["mean_accuracy"],
            "avg_actions": r["avg_actions"],
        }
        for r in per_budget_summary
    ]

    ranking_by_budget = []
    per_budget_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in per_budget_summary:
        per_budget_groups[int(row["budget"])].append(row)
    for budget in sorted(per_budget_groups.keys()):
        rows = sorted(per_budget_groups[budget], key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))
        for rank, row in enumerate(rows, start=1):
            ranking_by_budget.append(
                {
                    "budget": budget,
                    "rank": rank,
                    "method": row["method"],
                    "method_class": row["method_class"],
                    "mean_accuracy": row["mean_accuracy"],
                    "avg_actions": row["avg_actions"],
                }
            )

    def _acc_for(method: str, budget: int) -> float:
        for r in per_budget_summary:
            if str(r["method"]) == method and int(r["budget"]) == budget:
                return float(r["mean_accuracy"])
        return 0.0

    head_to_head = []
    tracked_methods = [m for m, _ in runnable_specs]
    for budget in budgets:
        f3 = _acc_for("strict_f3", budget)
        gate = _acc_for("strict_gate1_cap_k6", budget)
        best_external = max([m for m in tracked_methods if m.startswith("external_")], key=lambda m: _acc_for(m, budget))
        best_external_acc = _acc_for(best_external, budget)
        head_to_head.append(
            {
                "budget": budget,
                "strict_f3_accuracy": f3,
                "strict_gate1_cap_k6_accuracy": gate,
                "delta_strict_f3_minus_strict_gate1_cap_k6": f3 - gate,
                "best_near_direct_external": best_external,
                "best_near_direct_external_accuracy": best_external_acc,
                "strict_f3_minus_best_external": f3 - best_external_acc,
                "strict_gate1_cap_k6_minus_best_external": gate - best_external_acc,
            }
        )

    trend_rows = []
    for method in tracked_methods:
        accs = [_acc_for(method, b) for b in budgets]
        trend_rows.append(
            {
                "method": method,
                "method_class": _method_class(method),
                "accuracy_budget_10": accs[0] if len(accs) > 0 else None,
                "accuracy_budget_12": accs[1] if len(accs) > 1 else None,
                "accuracy_budget_14": accs[2] if len(accs) > 2 else None,
                "delta_10_to_14": (accs[-1] - accs[0]) if len(accs) >= 2 else None,
                "monotonic_non_decreasing": all(accs[i + 1] >= accs[i] for i in range(len(accs) - 1)),
            }
        )

    stability_flags = {
        "strict_f3_wins_all_extended_budgets": all(_acc_for("strict_f3", b) >= _acc_for("strict_gate1_cap_k6", b) for b in budgets),
        "strict_gate1_cap_k6_improves_with_budget": _acc_for("strict_gate1_cap_k6", budgets[-1]) >= _acc_for("strict_gate1_cap_k6", budgets[0]),
        "strict_f3_improves_with_budget": _acc_for("strict_f3", budgets[-1]) >= _acc_for("strict_f3", budgets[0]),
    }

    _write_csv(out_dir / "per_case_outcomes.csv", per_case_rows)
    _write_csv(out_dir / "comparison_table.csv", comparison_table)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget_summary)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset_summary)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed_summary)
    _write_csv(out_dir / "budget_performance_frontier.csv", frontier)
    _write_csv(out_dir / "method_ranking_by_budget.csv", ranking_by_budget)
    _write_csv(out_dir / "head_to_head_summary.csv", head_to_head)
    _write_csv(out_dir / "method_budget_trends.csv", trend_rows)
    if excluded_methods:
        _write_csv(out_dir / "excluded_methods.csv", excluded_methods)

    manifest = {
        "artifact_family": "extended_budget_frontier",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_extended_budget_frontier_robustness.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "source_surface_reference": "outputs/canonical_full_method_ranking_20260421T212948Z",
        "evaluation_contract": {
            "datasets": DATASETS,
            "seeds": seeds,
            "budgets": budgets,
            "subset_size_per_dataset_seed": SUBSET_SIZE,
            "methods_requested": [m for m, _ in METHOD_SPECS],
            "methods_runnable": [m for m, _ in runnable_specs],
        },
        "stability_flags": stability_flags,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    note_lines = [
        "# Extended budget frontier robustness note",
        "",
        f"This bundle extends the manuscript-facing budget study to budgets {','.join(str(b) for b in budgets)} using the same matched dataset contract as the canonical full ranking surface (datasets: gsm8k, MATH-500, aime_2024; subset size: 20), with configurable seed coverage.",
        f"- Seeds used: `{','.join(str(s) for s in seeds)}`.",
        "",
        "## Conservative decision interpretation",
        f"- strict_f3 wins all extended budgets: **{stability_flags['strict_f3_wins_all_extended_budgets']}**.",
        f"- strict_f3 improves from budget 10 to 14: **{stability_flags['strict_f3_improves_with_budget']}**.",
        f"- strict_gate1_cap_k6 improves from budget 10 to 14: **{stability_flags['strict_gate1_cap_k6_improves_with_budget']}**.",
        "- This extension is appendix/robustness-only by default and does not overwrite canonical 4/6/8 paper artifacts.",
        "",
        "## Key outputs",
        "- per-case: `per_case_outcomes.csv`",
        "- aggregate: `comparison_table.csv`, `per_budget_summary.csv`, `per_dataset_summary.csv`, `per_seed_summary.csv`",
        "- frontier + ranking: `budget_performance_frontier.csv`, `method_ranking_by_budget.csv`",
        "- head-to-head + trends: `head_to_head_summary.csv`, `method_budget_trends.csv`",
    ]
    (out_dir / "stability_note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
