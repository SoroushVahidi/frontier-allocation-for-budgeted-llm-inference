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

import importlib.util

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.hf_datasets import check_hf_dataset_access
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

DATASETS = ["Idavidrein/gpqa"]
SEEDS = [11, 23]
BUDGETS = [4, 6, 8, 10, 12, 14]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]


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


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_science_anchor", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def _parse_int_list(raw: str) -> list[int]:
    return sorted({int(x.strip()) for x in raw.split(",") if x.strip()})


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


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


def _method_class(method: str) -> str:
    return "near_direct_external" if method.startswith("external_") else "inhouse"


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty csv: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _aggregate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    out: list[dict[str, Any]] = []
    for key, vals in sorted(grouped.items()):
        method = str(vals[0].get("method", ""))
        rec: dict[str, Any] = {k: v for k, v in zip(keys, key)}
        rec.update(
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
                "gold_in_tree_rate": _mean([float(v["gold_in_tree"]) for v in vals]),
                "repeated_same_family_case_rate": _mean([float(v["repeated_same_family_present"]) for v in vals]),
            }
        )
        out.append(rec)
    return out


def _run_method(method_public: str, method_runtime: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = _stable_seed("science_anchor_robustness", method_public, dataset, seed, budget, example.example_id)
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
    final_nodes = [observed._snapshot(branch) for _, branch in sorted(observed.registry.items(), key=lambda kv: kv[0])]

    repair = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    answer = canonicalize_answer(repair.get("surfaced_final_answer_raw"), dataset=dataset)
    gold = canonicalize_answer(str(example.answer), dataset=dataset)

    gold_in_tree = bool(gold is not None and any(n.get("predicted_answer_normalized") == gold for n in final_nodes))
    output_mismatch = bool(gold_in_tree and (repair.get("chosen_final_node_answer_canonical") == gold) and (answer != gold))
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Run single science-anchor robustness extension on matched-style substrate.")
    ap.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    ap.add_argument("--datasets", default=",".join(DATASETS))
    ap.add_argument("--seeds", default=",".join(str(x) for x in SEEDS))
    ap.add_argument("--budgets", default=",".join(str(x) for x in BUDGETS))
    ap.add_argument("--subset-size", type=int, default=SUBSET_SIZE)
    args = ap.parse_args()

    datasets = _parse_list(args.datasets)
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)

    access = [check_hf_dataset_access(d) for d in datasets]
    blocked = [a for a in access if not bool(a.get("ok"))]
    if blocked:
        raise RuntimeError(f"Blocked dataset access: {blocked}")

    out_dir = REPO_ROOT / "outputs" / f"science_anchor_robustness_{args.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_specs = [(public, _runtime_method(full)) for public, full in METHOD_SPECS]
    probe_rng = random.Random(0)
    probe = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=probe_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        budgets[0],
        ADAPTIVE_GRID,
        probe_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    runnable = [(p, r) for p, r in runtime_specs if r in probe]
    excluded = [
        {"method": p, "runtime_key": r, "reason": "runtime_key_not_available"}
        for p, r in runtime_specs
        if r not in probe
    ]

    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                for ex in examples:
                    for public, runtime in runnable:
                        rows.append(_run_method(public, runtime, dataset, seed, budget, ex))

    comparison = _aggregate(rows, ["method"])
    comparison.sort(key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))
    per_budget = _aggregate(rows, ["budget", "method"])
    per_budget.sort(key=lambda r: (int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"])))
    per_method = comparison
    per_seed = _aggregate(rows, ["seed", "budget", "method"])
    per_seed.sort(key=lambda r: (int(r["seed"]), int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"])))
    per_dataset = _aggregate(rows, ["dataset", "budget", "method"])
    per_dataset.sort(key=lambda r: (str(r["dataset"]), int(r["budget"]), -float(r["mean_accuracy"]), str(r["method"])))

    internal = ["strict_f3", "strict_gate1_cap_k6", "strict_f2"]
    pair_rows: list[dict[str, Any]] = []
    for b in budgets:
        slice_rows = {str(r["method"]): r for r in per_budget if int(r["budget"]) == b}
        for a, c in [("strict_f3", "strict_gate1_cap_k6"), ("strict_f3", "strict_f2"), ("strict_gate1_cap_k6", "strict_f2")]:
            if a in slice_rows and c in slice_rows:
                ra, rc = slice_rows[a], slice_rows[c]
                pair_rows.append(
                    {
                        "budget": b,
                        "method_a": a,
                        "method_b": c,
                        "delta_mean_accuracy_a_minus_b": float(ra["mean_accuracy"] - rc["mean_accuracy"]),
                        "delta_absent_from_tree_rate_a_minus_b": float(ra["absent_from_tree_rate"] - rc["absent_from_tree_rate"]),
                        "delta_present_not_selected_rate_a_minus_b": float(ra["present_not_selected_rate"] - rc["present_not_selected_rate"]),
                        "delta_output_layer_mismatch_rate_a_minus_b": float(ra["output_layer_mismatch_rate"] - rc["output_layer_mismatch_rate"]),
                        "delta_repeated_same_family_case_rate_a_minus_b": float(ra["repeated_same_family_case_rate"] - rc["repeated_same_family_case_rate"]),
                    }
                )

    _write_csv(out_dir / "per_case_outcomes.csv", rows)
    _write_csv(out_dir / "comparison_table.csv", comparison)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget)
    _write_csv(out_dir / "per_method_summary.csv", per_method)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset)
    _write_csv(out_dir / "pairwise_mechanism_head_to_head.csv", pair_rows)

    # note
    def _acc(method: str, budget: int) -> float:
        for r in per_budget:
            if str(r["method"]) == method and int(r["budget"]) == budget:
                return float(r["mean_accuracy"])
        return 0.0

    high_budgets = [b for b in budgets if b >= 10]
    gate_high = sum(_acc("strict_gate1_cap_k6", b) for b in high_budgets)
    f3_high = sum(_acc("strict_f3", b) for b in high_budgets)
    f2_high = sum(_acc("strict_f2", b) for b in high_budgets)
    if gate_high >= max(f3_high, f2_high):
        gate_high_verdict = "stronger_on_high_budget_slice"
    elif gate_high >= f3_high:
        gate_high_verdict = "stronger_than_strict_f3_but_not_top_overall"
    else:
        gate_high_verdict = "not_stronger_on_high_budget_slice"

    f3_468 = [_acc("strict_f3", b) for b in budgets if b in {4, 6, 8}]
    gate_468 = [_acc("strict_gate1_cap_k6", b) for b in budgets if b in {4, 6, 8}]
    f2_468 = [_acc("strict_f2", b) for b in budgets if b in {4, 6, 8}]
    f3_pref_preserved = bool(f3_468) and all(f3 >= max(g, f2) for f3, g, f2 in zip(f3_468, gate_468, f2_468))

    dominant_mechanism = "mixed_or_not_assessed"
    f3_gate_rows = [r for r in pair_rows if r["method_a"] == "strict_f3" and r["method_b"] == "strict_gate1_cap_k6" and r["budget"] in high_budgets]
    if f3_gate_rows:
        abs_mag = sum(abs(float(r["delta_absent_from_tree_rate_a_minus_b"])) for r in f3_gate_rows)
        pns_mag = sum(abs(float(r["delta_present_not_selected_rate_a_minus_b"])) for r in f3_gate_rows)
        olm_mag = sum(abs(float(r["delta_output_layer_mismatch_rate_a_minus_b"])) for r in f3_gate_rows)
        if (abs_mag + pns_mag) > olm_mag:
            dominant_mechanism = "tree_entry_plus_selection"

    lines = [
        "# Science-anchor robustness note",
        "",
        "This bundle is appendix/robustness-only and does not alter canonical main-paper 4/6/8 artifacts.",
        f"- dataset(s): {datasets}",
        f"- budgets: {budgets}",
        f"- seeds: {seeds}",
        f"- subset_size: {args.subset_size}",
        "",
        "## Direct answers",
        f"1. Manuscript-facing preference for strict_f3 on this science anchor: {'preserved' if f3_pref_preserved else 'weakened_or_unresolved'}.",
        f"2. strict_gate1_cap_k6 high-budget strength (10/12/14): {gate_high_verdict} (sum_acc: gate={gate_high:.4f}, f3={f3_high:.4f}, f2={f2_high:.4f}).",
        f"3. strict_f2 competitiveness: {'yes' if f2_high >= max(gate_high, f3_high) else 'yes_but_not_top'} (high-budget sum_acc={f2_high:.4f}).",
        f"4. Dominant mechanism for high-budget strict_f3-vs-gate1 differences: {dominant_mechanism}.",
        "5. Paper strategy: keep appendix-only; do not alter canonical 4/6/8 manuscript contracts from this single science-anchor run.",
    ]
    (out_dir / "conservative_interpretation_note.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "science_anchor_robustness",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_science_anchor_robustness.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "evaluation_contract": {
            "datasets": datasets,
            "seeds": seeds,
            "budgets": budgets,
            "subset_size_per_dataset_seed": args.subset_size,
            "methods_requested": [m for m, _ in METHOD_SPECS],
            "methods_runnable": [m for m, _ in runnable],
        },
        "dataset_access_checks": access,
        "analysis_files": [
            "per_case_outcomes.csv",
            "comparison_table.csv",
            "per_budget_summary.csv",
            "per_method_summary.csv",
            "per_seed_summary.csv",
            "per_dataset_summary.csv",
            "pairwise_mechanism_head_to_head.csv",
            "conservative_interpretation_note.md",
        ],
        "appendix_only": True,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
