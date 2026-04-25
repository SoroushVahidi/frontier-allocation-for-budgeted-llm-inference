#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import classify_question_shape
from experiments.data import PilotExample
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_case_split_eval", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
PUBLIC_TO_RUNTIME = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
}

TARGET_METHODS = [
    "strict_f3",
    "strict_f3_case_split_direction_aware_v1",
    "strict_f3_case_split_direction_aware_v1_no_delayed_commit",
    "strict_f3_case_split_direction_aware_v1_no_stronger_repeat_family_penalty",
    "strict_f3_case_split_direction_aware_v1_no_unresolved_branch_preservation",
    "strict_f3_case_split_direction_aware_v1_detector_off",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
    "external_l1_max",
    "external_tale_prompt_budgeting",
    "external_s1_budget_forcing",
    "tot_bfs_matched_budget",
    "tot_beam_matched_budget",
    "tot_dfs_matched_budget",
    "self_consistency_3",
]


def _stable_seed(*parts: Any) -> int:
    text = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _aggregate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    out: list[dict[str, Any]] = []
    for k, vals in sorted(grouped.items()):
        row = {name: value for name, value in zip(keys, k)}
        row.update(
            {
                "n_cases": len(vals),
                "mean_accuracy": _mean([float(v["is_correct"]) for v in vals]),
                "avg_actions": _mean([float(v["actions_used"]) for v in vals]),
                "absent_from_tree_rate": _mean([float(v["absent_from_tree"]) for v in vals]),
                "present_not_selected_rate": _mean([float(v["present_not_selected"]) for v in vals]),
                "output_layer_mismatch_rate": _mean([float(v["output_layer_mismatch"]) for v in vals]),
            }
        )
        out.append(row)
    return out


def _runtime_for(method: str) -> str:
    return PUBLIC_TO_RUNTIME.get(method, method)


def _paired_difference(rows: list[dict[str, Any]], a: str, b: str) -> dict[str, Any]:
    idx = {
        (r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"], r["method"]): int(r["is_correct"]) for r in rows
    }
    diffs: list[float] = []
    for key, av in idx.items():
        d, s, budget, ex, m = key
        if m != a:
            continue
        other_key = (d, s, budget, ex, b)
        if other_key in idx:
            diffs.append(float(av - idx[other_key]))
    return {
        "method_a": a,
        "method_b": b,
        "n_paired": len(diffs),
        "mean_difference": _mean(diffs),
        "a_win_rate": _mean([1.0 if x > 0 else 0.0 for x in diffs]),
        "b_win_rate": _mean([1.0 if x < 0 else 0.0 for x in diffs]),
        "tie_rate": _mean([1.0 if x == 0 else 0.0 for x in diffs]),
    }


def _run_case(specs: dict[str, Any], ex: PilotExample, dataset: str, seed: int, budget: int, methods: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    qlabel = classify_question_shape(ex.question)
    is_case_split = int(qlabel in {"counting_combinatorics", "case_split"})
    for method in methods:
        runtime = _runtime_for(method)
        if runtime not in specs:
            continue
        ctrl = specs[runtime]
        res = ctrl.run(ex.question, ex.answer)
        gen = getattr(ctrl, "generator", None)
        if gen is None:
            continue
        final_nodes = [gen._snapshot(b) for _, b in sorted(gen.registry.items(), key=lambda kv: kv[0])]  # type: ignore[attr-defined]
        rep = choose_repair_answer(
            final_nodes=final_nodes,
            selected_group_hint=(res.metadata or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        ans = canonicalize_answer(rep.get("surfaced_final_answer_raw"), dataset=dataset)
        gold = canonicalize_answer(str(ex.answer), dataset=dataset)
        is_correct = int(ans == gold and ans is not None)
        gold_in_tree = bool(gold is not None and any(n.get("predicted_answer_normalized") == gold for n in final_nodes))
        output_mismatch = bool(gold_in_tree and (rep.get("chosen_final_node_answer_canonical") == gold) and (ans != gold))
        extraction_mismatch = bool(
            rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical")
            or rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical")
        )
        if not gold_in_tree:
            failure = "absent_from_tree"
        elif output_mismatch or extraction_mismatch:
            failure = "output_layer_mismatch"
        elif is_correct:
            failure = "correct"
        else:
            failure = "present_not_selected"
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": str(ex.example_id),
                "method": method,
                "question_shape_label": qlabel,
                "is_case_split_target": is_case_split,
                "is_correct": is_correct,
                "actions_used": int(res.actions_used),
                "expansions": int(res.expansions),
                "verifications": int(res.verifications),
                "failure_type": failure,
                "absent_from_tree": int(failure == "absent_from_tree"),
                "present_not_selected": int(failure == "present_not_selected"),
                "output_layer_mismatch": int(failure == "output_layer_mismatch"),
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Offline eval for strict_f3_case_split_direction_aware_v1")
    p.add_argument("--seeds", default="11,23,37,41,53")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--subset-size", type=int, default=40)
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = p.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    budgets = [int(x) for x in args.budgets.split(",") if x.strip()]

    out_dir = REPO_ROOT / "outputs" / f"case_split_direction_aware_offline_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    resolved_methods: set[str] = set()

    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                rng_loop = random.Random(_stable_seed("case_split_eval", dataset, seed, budget) & 0xFFFFFFFF)

                def generator_factory() -> Any:
                    rng_cell = random.Random(_stable_seed("case_split_eval_cell", dataset, seed, budget, rng_loop.random()) & 0xFFFFFFFF)
                    return TW.ObservedGenerator(
                        SimulatedBranchGenerator(rng=rng_cell, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
                    )

                specs = build_frontier_strategies(
                    generator_factory,
                    budget,
                    [1],
                    rng_loop,
                    use_openai_api=False,
                    include_broad_diversity_aggregation_methods=True,
                    include_external_l1_baseline=True,
                    include_external_tale_baseline=True,
                    include_external_s1_baseline=True,
                )
                methods = [m for m in TARGET_METHODS if _runtime_for(m) in specs]
                resolved_methods.update(methods)
                for ex in examples:
                    per_case.extend(_run_case(specs, ex, dataset, seed, budget, methods))

    _write_csv(out_dir / "per_case_outcomes.csv", per_case)

    main_summary = _aggregate(per_case, ["method"])
    per_dataset_summary = _aggregate(per_case, ["dataset", "method"])
    per_budget_summary = _aggregate(per_case, ["budget", "method"])
    per_seed_summary = _aggregate(per_case, ["seed", "method"])
    case_subset = _aggregate([r for r in per_case if int(r["is_case_split_target"]) == 1], ["method"])
    non_case_subset = _aggregate([r for r in per_case if int(r["is_case_split_target"]) == 0], ["method"])
    failure_decomp = _aggregate([r for r in per_case if int(r["is_correct"]) == 0], ["method", "failure_type"])

    pair_specs = [
        ("strict_f3_case_split_direction_aware_v1", "strict_f3"),
        ("strict_f3_case_split_direction_aware_v1", "strict_gate1_cap_k6"),
        ("strict_f3_case_split_direction_aware_v1", "strict_f3_anti_collapse_weak_v1"),
        ("strict_f3_case_split_direction_aware_v1", "external_l1_max"),
    ]
    pairwise = [_paired_difference(per_case, a, b) for a, b in pair_specs if a in resolved_methods and b in resolved_methods]

    ablations = [
        "strict_f3_case_split_direction_aware_v1",
        "strict_f3_case_split_direction_aware_v1_no_delayed_commit",
        "strict_f3_case_split_direction_aware_v1_no_stronger_repeat_family_penalty",
        "strict_f3_case_split_direction_aware_v1_no_unresolved_branch_preservation",
        "strict_f3_case_split_direction_aware_v1_detector_off",
        "strict_f3",
    ]
    ablation_rows = [r for r in main_summary if str(r.get("method")) in set(ablations)]

    by_method = {str(r["method"]): r for r in main_summary}
    cs = by_method.get("strict_f3_case_split_direction_aware_v1", {})
    f3 = by_method.get("strict_f3", {})
    case_by_method = {str(r["method"]): r for r in case_subset}
    non_case_by_method = {str(r["method"]): r for r in non_case_subset}
    claim_rows = [
        {
            "claim": "overall_improvement_vs_strict_f3",
            "delta": float(cs.get("mean_accuracy", 0.0)) - float(f3.get("mean_accuracy", 0.0)),
            "status": "candidate_main_paper" if (float(cs.get("mean_accuracy", 0.0)) - float(f3.get("mean_accuracy", 0.0))) >= 0.01 else "exploratory_or_appendix",
        },
        {
            "claim": "case_subset_improvement",
            "delta": float(case_by_method.get("strict_f3_case_split_direction_aware_v1", {}).get("mean_accuracy", 0.0))
            - float(case_by_method.get("strict_f3", {}).get("mean_accuracy", 0.0)),
            "status": "improved" if float(case_by_method.get("strict_f3_case_split_direction_aware_v1", {}).get("mean_accuracy", 0.0)) >= float(case_by_method.get("strict_f3", {}).get("mean_accuracy", 0.0)) else "worse",
        },
        {
            "claim": "non_case_subset_harm",
            "delta": float(non_case_by_method.get("strict_f3_case_split_direction_aware_v1", {}).get("mean_accuracy", 0.0))
            - float(non_case_by_method.get("strict_f3", {}).get("mean_accuracy", 0.0)),
            "status": "no_material_harm" if float(non_case_by_method.get("strict_f3_case_split_direction_aware_v1", {}).get("mean_accuracy", 0.0)) >= float(non_case_by_method.get("strict_f3", {}).get("mean_accuracy", 0.0)) - 0.005 else "harm_observed",
        },
    ]

    _write_csv(out_dir / "main_summary.csv", main_summary)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset_summary)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget_summary)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed_summary)
    _write_csv(out_dir / "case_split_subset_summary.csv", case_subset)
    _write_csv(out_dir / "non_case_split_subset_summary.csv", non_case_subset)
    _write_csv(out_dir / "failure_decomposition.csv", failure_decomp)
    _write_csv(out_dir / "pairwise_comparisons.csv", pairwise)
    _write_csv(out_dir / "ablation_summary.csv", ablation_rows)
    _write_csv(out_dir / "claim_safety_table.csv", claim_rows)

    manifest = {
        "timestamp": args.timestamp,
        "datasets": DATASETS,
        "budgets": budgets,
        "seeds": seeds,
        "subset_size": args.subset_size,
        "methods_requested": TARGET_METHODS,
        "methods_resolved": sorted(resolved_methods),
        "api_policy": "offline_simulator_only_no_paid_or_generative_external_api",
        "command": "python scripts/run_case_split_direction_aware_offline_eval.py",
        "outputs": [
            "manifest.json",
            "per_case_outcomes.csv",
            "main_summary.csv",
            "per_dataset_summary.csv",
            "per_budget_summary.csv",
            "per_seed_summary.csv",
            "case_split_subset_summary.csv",
            "non_case_split_subset_summary.csv",
            "failure_decomposition.csv",
            "pairwise_comparisons.csv",
            "ablation_summary.csv",
            "claim_safety_table.csv",
            "README.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    readme_lines = [
        f"# case_split_direction_aware_offline_eval_{args.timestamp}",
        "",
        "Offline matched action-budget evaluation artifact for strict_f3_case_split_direction_aware_v1.",
        "",
        f"- Datasets: {', '.join(DATASETS)}",
        f"- Budgets: {', '.join(str(x) for x in budgets)}",
        f"- Seeds: {', '.join(str(x) for x in seeds)}",
        f"- Subset size per dataset-seed: {args.subset_size}",
    ]
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    def _acc(method: str, rows: list[dict[str, Any]]) -> float:
        for r in rows:
            if str(r.get("method")) == method:
                return float(r.get("mean_accuracy", 0.0))
        return 0.0

    report_lines = [
        f"# CASE_SPLIT_DIRECTION_AWARE_OFFLINE_EVAL_{args.timestamp}",
        "",
        "## Setup",
        f"- Output directory: `outputs/case_split_direction_aware_offline_eval_{args.timestamp}/`.",
        f"- Datasets: {', '.join(DATASETS)}.",
        f"- Budgets: {', '.join(str(x) for x in budgets)}.",
        f"- Seeds: {', '.join(str(x) for x in seeds)}.",
        "",
        "## Answers to required questions",
        f"1. Overall improvement over strict_f3: delta = {_acc('strict_f3_case_split_direction_aware_v1', main_summary) - _acc('strict_f3', main_summary):+.4f}.",
        f"2. Improvement on detected counting/case-split subset: delta = {_acc('strict_f3_case_split_direction_aware_v1', case_subset) - _acc('strict_f3', case_subset):+.4f}.",
        f"3. Absent-from-tree reduction: delta = {next((float(r['absent_from_tree_rate']) for r in main_summary if r['method']=='strict_f3_case_split_direction_aware_v1'), 0.0) - next((float(r['absent_from_tree_rate']) for r in main_summary if r['method']=='strict_f3'), 0.0):+.4f} (negative is better).",
        f"4. Non-case-split harm check: delta = {_acc('strict_f3_case_split_direction_aware_v1', non_case_subset) - _acc('strict_f3', non_case_subset):+.4f}.",
        f"5. Versus strict_gate1_cap_k6 / strict_f3_anti_collapse_weak_v1: deltas = {_acc('strict_f3_case_split_direction_aware_v1', main_summary) - _acc('strict_gate1_cap_k6', main_summary):+.4f}, {_acc('strict_f3_case_split_direction_aware_v1', main_summary) - _acc('strict_f3_anti_collapse_weak_v1', main_summary):+.4f}.",
        f"6. Versus external_l1_max on matched offline budget: delta = {_acc('strict_f3_case_split_direction_aware_v1', main_summary) - _acc('external_l1_max', main_summary):+.4f}.",
        f"7. Manuscript candidacy threshold check (>=1pp): {'candidate_main_paper' if (_acc('strict_f3_case_split_direction_aware_v1', main_summary) - _acc('strict_f3', main_summary)) >= 0.01 else 'appendix_or_exploratory'}.",
        "8. Failure interpretation: see `failure_decomposition.csv` and `pairwise_comparisons.csv` for where gains/losses concentrate.",
    ]
    (REPO_ROOT / "docs" / f"CASE_SPLIT_DIRECTION_AWARE_OFFLINE_EVAL_{args.timestamp}.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
