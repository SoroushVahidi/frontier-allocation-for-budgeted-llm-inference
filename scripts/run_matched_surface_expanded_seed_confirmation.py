#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
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

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]

METHOD_RUNTIME_MAP = {
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
    "strict_f2": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1",
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
    "external_l1_exact": "external_l1_exact",
    "external_l1_max": "external_l1_max",
}


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_expanded_seed_confirmation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stable_seed(*parts: Any) -> int:
    joined = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16], 16)


def _parse_int_csv(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _run_observed(method: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    runtime_method = METHOD_RUNTIME_MAP[method]
    run_seed = _stable_seed("matched_surface_expanded_seed_confirmation", method, dataset, example.example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    specs = build_frontier_strategies(
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
    if runtime_method not in specs:
        raise KeyError(f"Runtime method key unavailable: {runtime_method}")
    result = specs[runtime_method].run(example.question, example.answer)

    final_nodes = []
    for _, branch in sorted(observed.registry.items(), key=lambda pair: pair[0]):
        final_nodes.append(observed._snapshot(branch))

    repair = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    predicted = canonicalize_answer(repair.get("surfaced_final_answer_raw"), dataset=dataset)
    gold = canonicalize_answer(str(example.answer), dataset=dataset)
    is_correct = int(predicted == gold and predicted is not None)

    return {
        "dataset": dataset,
        "seed": int(seed),
        "budget": int(budget),
        "example_id": str(example.example_id),
        "method": method,
        "is_correct": is_correct,
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Expanded-seed matched-surface confirmation for manuscript-facing internal decision.")
    parser.add_argument("--run-id", default=_utc_run_id())
    parser.add_argument("--seeds", default="11,23,37,47,59")
    args = parser.parse_args()

    seeds = _parse_int_csv(args.seeds)
    methods = [
        "strict_f3",
        "strict_gate1_cap_k6",
        "strict_f2",
        "external_s1_budget_forcing",
        "external_tale_prompt_budgeting",
        "external_l1_exact",
        "external_l1_max",
    ]
    out_dir = REPO_ROOT / "outputs" / f"matched_surface_expanded_seed_confirmation_{args.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                for example in examples:
                    for method in methods:
                        rows.append(_run_observed(method, dataset, seed, budget, example))

    aggregate_df_rows: list[dict[str, Any]] = []
    per_seed_rows: list[dict[str, Any]] = []
    per_budget_rows: list[dict[str, Any]] = []
    h2h_rows: list[dict[str, Any]] = []

    # Aggregate by method.
    for method in methods:
        mrows = [r for r in rows if r["method"] == method]
        if not mrows:
            continue
        n = len(mrows)
        aggregate_df_rows.append(
            {
                "method": method,
                "n_cases": n,
                "mean_accuracy": sum(int(r["is_correct"]) for r in mrows) / n,
                "avg_actions": sum(float(r["actions"]) for r in mrows) / n,
                "avg_expansions": sum(float(r["expansions"]) for r in mrows) / n,
                "avg_verifications": sum(float(r["verifications"]) for r in mrows) / n,
            }
        )

    # Per-seed summary.
    for seed in seeds:
        for method in methods:
            srows = [r for r in rows if r["seed"] == seed and r["method"] == method]
            if not srows:
                continue
            n = len(srows)
            per_seed_rows.append(
                {
                    "seed": int(seed),
                    "method": method,
                    "n_cases": n,
                    "mean_accuracy": sum(int(r["is_correct"]) for r in srows) / n,
                    "avg_actions": sum(float(r["actions"]) for r in srows) / n,
                }
            )

    # Per-budget summary.
    for budget in BUDGETS:
        for method in methods:
            brows = [r for r in rows if r["budget"] == budget and r["method"] == method]
            if not brows:
                continue
            n = len(brows)
            per_budget_rows.append(
                {
                    "budget": int(budget),
                    "method": method,
                    "n_cases": n,
                    "mean_accuracy": sum(int(r["is_correct"]) for r in brows) / n,
                    "avg_actions": sum(float(r["actions"]) for r in brows) / n,
                }
            )

    # strict_f3 vs strict_gate1_cap_k6 head-to-head.
    index = {
        (r["dataset"], r["seed"], r["budget"], r["example_id"], r["method"]): r
        for r in rows
        if r["method"] in {"strict_f3", "strict_gate1_cap_k6"}
    }
    for dataset in DATASETS:
        for seed in seeds:
            for budget in BUDGETS:
                example_ids = sorted(
                    {
                        str(r["example_id"])
                        for r in rows
                        if r["dataset"] == dataset and r["seed"] == seed and r["budget"] == budget
                    }
                )
                for example_id in example_ids:
                    f3 = index.get((dataset, seed, budget, example_id, "strict_f3"))
                    gk6 = index.get((dataset, seed, budget, example_id, "strict_gate1_cap_k6"))
                    if f3 is None or gk6 is None:
                        continue
                    f3_correct = int(f3["is_correct"])
                    gk6_correct = int(gk6["is_correct"])
                    h2h_rows.append(
                        {
                            "dataset": dataset,
                            "seed": int(seed),
                            "budget": int(budget),
                            "example_id": example_id,
                            "strict_f3_is_correct": f3_correct,
                            "strict_gate1_cap_k6_is_correct": gk6_correct,
                            "strict_f3_minus_strict_gate1_cap_k6": f3_correct - gk6_correct,
                        }
                    )

    aggregate_df_rows.sort(key=lambda row: (-float(row["mean_accuracy"]), row["method"]))
    _write_csv(out_dir / "aggregate_comparison.csv", aggregate_df_rows)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed_rows)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget_rows)
    _write_csv(out_dir / "head_to_head_strict_f3_vs_strict_gate1_cap_k6.csv", h2h_rows)

    agg_lookup = {row["method"]: row for row in aggregate_df_rows}
    f3_acc = float(agg_lookup.get("strict_f3", {}).get("mean_accuracy", 0.0))
    gk6_acc = float(agg_lookup.get("strict_gate1_cap_k6", {}).get("mean_accuracy", 0.0))
    delta = f3_acc - gk6_acc
    winner = "strict_f3" if delta > 0 else "strict_gate1_cap_k6" if delta < 0 else "tie"
    strength = "strengthens" if winner == "strict_f3" and abs(delta) >= 0.005556 else "mixed_or_unchanged"

    config_payload = {
        "contract_name": "canonical manuscript-facing matched surface rerun",
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "seeds": seeds,
        "subset_size_per_dataset_seed": SUBSET_SIZE,
        "methods": methods,
        "notes": "Expanded-seed independent rerun on same manuscript-facing matched contract class; includes fair near-direct externals present in canonical runner.",
    }
    manifest_payload = {
        "artifact_family": "matched_surface_expanded_seed_confirmation",
        "run_id": args.run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_file": "config.json",
        "output_files": [
            "manifest.json",
            "config.json",
            "aggregate_comparison.csv",
            "per_seed_summary.csv",
            "per_budget_summary.csv",
            "head_to_head_strict_f3_vs_strict_gate1_cap_k6.csv",
            "stability_note.md",
        ],
    }
    _write_json(out_dir / "config.json", config_payload)
    _write_json(out_dir / "manifest.json", manifest_payload)

    note_lines = [
        "# Stability note",
        "",
        "- Contract: same manuscript-facing matched datasets and budget range as canonical matched-surface family (GSM8K, MATH-500, AIME-2024; budgets 4/6/8; subset size 20).",
        f"- Expanded seed set used: {seeds}.",
        "- Internal focus methods: strict_f3, strict_gate1_cap_k6, strict_f2.",
        "- Fair near-direct external baselines included: external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max.",
        f"- Aggregate strict_f3 accuracy: {f3_acc:.6f}.",
        f"- Aggregate strict_gate1_cap_k6 accuracy: {gk6_acc:.6f}.",
        f"- Delta (strict_f3 - strict_gate1_cap_k6): {delta:.6f}.",
        f"- Winner on this expanded-seed rerun: {winner}.",
        f"- Evidence status relative to prior manuscript-facing winner: {strength}.",
    ]
    (out_dir / "stability_note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir.relative_to(REPO_ROOT)), "seeds": seeds, "winner": winner, "delta": delta}, indent=2))


if __name__ == "__main__":
    main()
