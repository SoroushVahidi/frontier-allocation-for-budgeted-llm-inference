#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "full_method_comparison_20260418"
LIGHT_ROOT = OUT / "light_all_methods"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def pick_light_runs() -> list[Path]:
    runs = sorted([p for p in LIGHT_ROOT.iterdir() if p.is_dir() and p.name >= "20260418T024432Z"])
    selected = []
    for run in runs:
        manifest = read_json(run / "manifest.json")
        if manifest.get("dataset") in {
            "openai/gsm8k",
            "HuggingFaceH4/MATH-500",
            "HuggingFaceH4/aime_2024",
            "olympiadbench",
        }:
            selected.append(run)
    return selected


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selected_runs = pick_light_runs()

    multistep = read_json(REPO / "outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json")
    completion = read_json(REPO / "outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/aggregate_comparison_summary.json")
    strict_summary = read_json(REPO / "outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_summary.json")
    strict_results = read_json(REPO / "outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_results.json")
    imported_summary = read_json(REPO / "outputs/imported_methodology_frontier_eval/20260417T000000Z/summary.json")
    imported_method_metrics = read_csv(REPO / "outputs/imported_methodology_frontier_eval/20260417T000000Z/method_metrics.csv")
    imported_oracle_gap = read_csv(REPO / "outputs/imported_methodology_frontier_eval/20260417T000000Z/oracle_gap_summary.csv")

    external_statuses = []
    for p in sorted((REPO / "outputs/external_baseline_completeness").glob("*_status.json")):
        payload = read_json(p)
        external_statuses.append(
            {
                "file": str(p.relative_to(REPO)),
                "baseline_key": payload.get("baseline_key", p.stem.replace("_status", "")),
                "status": payload.get("status"),
                "integration_kind": payload.get("integration_kind"),
                "comparability_scope": payload.get("protocol", {}).get("comparability_scope"),
            }
        )

    light_rows = []
    light_summary_rows = []
    light_method_summary = []
    for run in selected_runs:
        manifest = read_json(run / "manifest.json")
        dataset = manifest["dataset"]
        per_seed = read_csv(run / "per_seed_method_metrics.csv")
        comparison = read_csv(run / "comparison_table.csv")
        per_method = read_csv(run / "per_method_summary.csv")
        for row in per_seed:
            row["dataset"] = dataset
            row["run_id"] = run.name
            light_rows.append(row)
        for row in comparison:
            row["dataset"] = dataset
            row["run_id"] = run.name
            light_summary_rows.append(row)
        for row in per_method:
            row["dataset"] = dataset
            row["run_id"] = run.name
            light_method_summary.append(row)

    # dataset slices from strict validation (full method + baselines)
    dataset_slice_acc = {}
    dataset_slice_cov = {}
    for row in strict_results["rows"]:
        full = row["variant_metrics"]["full_method"]["dataset_slices"]
        pairwise = row["pairwise_binary_baseline"]
        proxy = row["penalized_marginal_proxy_baseline"]
        for ds, vals in full.items():
            dataset_slice_acc.setdefault(ds, []).append(float(vals["accepted_pair_accuracy"]))
            dataset_slice_cov.setdefault(ds, []).append(float(vals["coverage"]))

    strict_dataset_table = []
    for ds in sorted(dataset_slice_acc):
        strict_dataset_table.append(
            {
                "dataset": ds,
                "method": "best_bounded_learned_branch_score_current",
                "accepted_pair_accuracy": mean(dataset_slice_acc[ds]),
                "coverage": mean(dataset_slice_cov[ds]),
            }
        )

    # Hard-slice table
    hard_slice_tables = {
        "multistep_validation": multistep["aggregate"],
        "strict_validation_variants": strict_summary["aggregate"]["variants"],
    }

    oracle_alignment_tables = {
        "completion_aware_policy_summary": completion["observability_run_policy_summary"],
        "completion_vs_best_bounded_learned": completion["comparison_vs_best_bounded_learned"],
        "imported_frontier_oracle_gap_rows": imported_oracle_gap,
    }

    # cost-quality + seed stability from light runs
    cost_quality = []
    for r in light_summary_rows:
        cost_quality.append(
            {
                "dataset": r["dataset"],
                "budget": int(r["budget"]),
                "method": r["method"],
                "group": r["group"],
                "mean_accuracy": float(r["mean_accuracy"]),
                "mean_avg_actions": float(r["mean_avg_actions"]),
                "mean_underspend_rate": float(r["mean_underspend_rate"]),
                "mean_budget_exhaustion_rate": float(r["mean_budget_exhaustion_rate"]),
            }
        )

    seed_stability = []
    for r in light_summary_rows:
        seed_stability.append(
            {
                "dataset": r["dataset"],
                "budget": int(r["budget"]),
                "method": r["method"],
                "std_accuracy": float(r["std_accuracy"]),
                "mean_accuracy": float(r["mean_accuracy"]),
                "n_seeds": 3,
            }
        )

    # semantic failures from fresh artifacts
    failure_tax = read_json(REPO / "outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418/failure_taxonomy_summary.json")
    worst_run_summary = read_json(REPO / "outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/run_summary.json")
    recoverability = read_json(REPO / "outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/recoverability_summary.json")

    semantic_failure = {
        "dominant_failure_taxonomy": failure_tax,
        "worst_casebook_run_summary": worst_run_summary,
        "recoverability_summary": recoverability,
    }

    # aggregate comparison view
    per_dataset_top = {}
    for ds in sorted({r["dataset"] for r in light_method_summary}):
        rows = [r for r in light_method_summary if r["dataset"] == ds]
        rows_sorted = sorted(rows, key=lambda x: float(x["mean_accuracy_over_budgets"]), reverse=True)
        per_dataset_top[ds] = rows_sorted[:5]

    aggregate_tables = {
        "our_method_definition": {
            "primary_recommended_scaffold": "multistep_k3_current as strongest bounded learned line, with bounded completion-aware correction in disagreement/near-tie slices",
            "best_bounded_learned_branch_score_current": strict_summary["aggregate"]["variants"]["full_method"],
            "multistep_k3_current": multistep["aggregate"]["multistep_k3"],
            "tie_aware_fallback_representative": "near_tie_two_stage_defer_calib_policy_20260417 (artifact-backed, small-sample)",
            "completion_aware_representative": "completion_aware_decision_eval_20260418",
        },
        "multistep_vs_baseline": multistep["comparison_vs_baseline"],
        "strict_validation_deltas": strict_summary["aggregate"]["deltas"],
        "top_methods_per_dataset_light_multi_dataset": per_dataset_top,
        "external_baseline_availability": external_statuses,
        "fixed_adaptive_oracle_reference_snapshot": {
            "summary": imported_summary,
            "method_metrics": imported_method_metrics,
        },
    }

    included_methods = {
        "our_methods": [
            "best_bounded_learned_branch_score_current(full_method variant in strict validation)",
            "multistep_k3_current",
            "completion_outside_gate/completion_tie_resolution/completion_bonus policies",
            "near_tie_two_stage_defer_calib_policy variants",
        ],
        "internal_baselines": [
            "baseline_current_matched",
            "baseline_all_pairs",
            "all_pairs_approx regime",
            "pairwise_binary_baseline",
            "penalized_marginal_proxy_baseline",
            "reasoning_greedy",
            "self_consistency_3",
            "reasoning_beam2",
            "verifier_guided_search",
            "program_of_thought",
            "adaptive_min_expand_{0,1,2}",
            "adaptive_budget_guarded",
        ],
        "external_baselines_runnable_in_repo": [
            "external_s1_budget_forcing (MODE A adapter)",
            "external_tale_prompt_budgeting (MODE A adapter)",
            "external_l1_exact (MODE A adapter)",
            "external_l1_max (MODE A adapter)",
        ],
        "external_adjacent_verified_import_only": [
            s["baseline_key"] for s in external_statuses if s["status"] == "runnable_adjacent"
        ],
        "reference_points": [
            "oracle_frontier_upper_bound",
            "fixed-budget baselines in imported frontier eval",
            "adaptive_budget_guarded",
        ],
        "not_available_or_blocked_for_direct_in_repo_comparison": [
            s["baseline_key"] for s in external_statuses if s["status"] in {"blocked", "link_only", "discuss_only"}
        ],
    }

    datasets = sorted({r["dataset"] for r in light_rows} | {r["dataset"] for r in strict_dataset_table})
    included_datasets = {
        "datasets_in_light_multi_dataset_run": sorted({r["dataset"] for r in light_rows}),
        "datasets_in_strict_validation_slices": sorted({r["dataset"] for r in strict_dataset_table}),
        "all_included_datasets": datasets,
    }

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": str(OUT.relative_to(REPO)),
        "source_artifacts": [
            "outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json",
            "outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_summary.json",
            "outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_results.json",
            "outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/aggregate_comparison_summary.json",
            "outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/completion_alignment_diagnostics.json",
            "outputs/imported_methodology_frontier_eval/20260417T000000Z/*",
            "outputs/external_baseline_completeness/*_status.json",
            "outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418/failure_taxonomy_summary.json",
            "outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/*.json",
            *[str((run / "manifest.json").relative_to(REPO)) for run in selected_runs],
        ],
        "new_runs_included": [str(run.relative_to(REPO)) for run in selected_runs],
        "assumptions": [
            "External baselines are adapters/adjacent imports unless explicitly direct-mode runnable; claims are restricted accordingly.",
            "Light multi-dataset runs are simulator-mode and for broad comparison coverage, not final paper-ready absolute performance.",
            "Strict-validation artifacts provide richer hard-slice and dataset-slice signals for learned branch-scoring methods.",
        ],
    }

    write_json(OUT / "manifest.json", manifest)
    write_json(OUT / "included_methods.json", included_methods)
    write_json(OUT / "included_datasets.json", included_datasets)
    write_json(OUT / "aggregate_comparison_tables.json", aggregate_tables)
    write_json(OUT / "per_dataset_tables.json", {
        "light_multi_dataset_method_summary": light_summary_rows,
        "strict_validation_dataset_slices": strict_dataset_table,
    })
    write_json(OUT / "hard_slice_tables.json", hard_slice_tables)
    write_json(OUT / "oracle_alignment_tables.json", oracle_alignment_tables)
    write_json(OUT / "cost_quality_tables.json", {"rows": cost_quality})
    write_json(OUT / "seed_stability_tables.json", {"rows": seed_stability})
    write_json(OUT / "semantic_failure_summary.json", semantic_failure)

    commands_md = """# Commands, assumptions, and caveats

## Commands run for this bundle
- python scripts/run_light_all_methods_comparison.py --dataset openai/gsm8k --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/MATH-500 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/aime_2024 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset olympiadbench --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/build_full_method_comparison_status_20260418.py

## Key assumptions
- Existing canonical branch-learning artifacts are treated as primary evidence for hard-slice and oracle-alignment behavior.
- External methods are included only when implemented, documented, or import-validated in this repository.
- Adjacent import baselines are explicitly labeled adjacent-only and not treated as direct control-space-equivalent reproductions.

## Major caveats
- Light multi-dataset comparisons are simulator-mode and should be interpreted conservatively.
- Imported methodology frontier reference snapshot currently uses a small gsm8k split.
- Some external baseline families remain blocked or only partially integrated (MODE B import dependence).
"""
    (OUT / "commands_assumptions_caveats.md").write_text(commands_md, encoding="utf-8")

    print(json.dumps({"status": "ok", "out": str(OUT.relative_to(REPO)), "runs": [r.name for r in selected_runs]}, indent=2))


if __name__ == "__main__":
    main()
