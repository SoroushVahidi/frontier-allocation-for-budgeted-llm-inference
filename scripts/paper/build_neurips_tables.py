#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from pathlib import Path
from statistics import mean

from scripts.paper.artifact_utils import (
    ADAPTIVE_HEURISTIC_METHODS,
    FIXED_METHODS,
    LEARNED_POLICY_CANDIDATES,
    Inputs,
    allocation_diversity_from_oracle,
    as_float,
    budget_buckets,
    ensure_output_dirs,
    fmt,
    load_inputs,
    read_csv,
    write_csv,
    write_tex_table,
    PAPER_TABLE_DIR,
)


def _load(inputs: Inputs):
    imported_method_metrics = read_csv(inputs.imported_run / "method_metrics.csv")
    imported_oracle_gap = read_csv(inputs.imported_run / "oracle_gap_summary.csv")
    imported_frontier = read_csv(inputs.imported_run / "budget_frontier_summary.csv")
    imported_summary = json.loads((inputs.imported_run / "summary.json").read_text(encoding="utf-8"))

    full_manifest = json.loads((inputs.full_bundle_run / "manifest.json").read_text(encoding="utf-8"))
    full_per_seed = read_csv(inputs.full_bundle_run / "per_seed_method_metrics.csv")
    full_per_method = read_csv(inputs.full_bundle_run / "per_method_metrics.csv")
    full_per_example = read_csv(inputs.full_bundle_run / "per_example_outcomes.csv")
    return {
        "imported_method_metrics": imported_method_metrics,
        "imported_oracle_gap": imported_oracle_gap,
        "imported_frontier": imported_frontier,
        "imported_summary": imported_summary,
        "full_manifest": full_manifest,
        "full_per_seed": full_per_seed,
        "full_per_method": full_per_method,
        "full_per_example": full_per_example,
    }


def build_task_controller_summary(data: dict) -> None:
    manifest = data["full_manifest"]
    per_method = data["full_per_method"]
    imported_summary = data["imported_summary"]

    families = sorted({r["family"] for r in per_method})
    methods = sorted({r["method"] for r in per_method})
    rows = []
    for ds in manifest.get("datasets", []):
        rows.append(
            {
                "dataset": ds,
                "n_eval_examples_per_seed": manifest.get("subset_size", ""),
                "n_seeds": len(manifest.get("seeds", [])),
                "budget_grid": ",".join(str(x) for x in manifest.get("budgets", [])),
                "controller_families": "|".join(families),
                "controller_methods": "|".join(methods),
                "cost_metric": "actions_used (reported as avg_actions)",
                "evaluation_metric": "accuracy",
                "oracle_metric": "gap_to_oracle and oracle_accuracy",
                "canonical_frontier_source": str(Path(imported_summary["files"]["method_metrics_csv"]).as_posix()),
            }
        )

    write_csv(PAPER_TABLE_DIR / "task_controller_summary.csv", rows)
    tex_rows = [
        [
            r["dataset"],
            str(r["n_eval_examples_per_seed"]),
            str(r["n_seeds"]),
            r["budget_grid"],
            "accuracy",
            "avg_actions",
        ]
        for r in rows
    ]
    write_tex_table(
        PAPER_TABLE_DIR / "task_controller_summary.tex",
        ["Dataset", "N/seed", "Seeds", "Budgets", "Eval", "Cost"],
        tex_rows,
        caption="Task/controller summary for fixed-budget frontier allocation artifacts.",
        label="tab:task_controller_summary",
    )


def _best_method_for_budget(rows: list[dict], budget: int, candidates: list[str]) -> dict | None:
    subset = [r for r in rows if int(r["budget"]) == budget and r["method"] in candidates]
    if not subset:
        return None
    return sorted(subset, key=lambda r: (as_float(r["accuracy"]), -as_float(r.get("avg_actions", 0.0))), reverse=True)[0]


def build_main_frontier_comparison(data: dict) -> list[dict]:
    rows = data["imported_method_metrics"]
    budgets = sorted({int(r["budget"]) for r in rows})
    bucket_map = budget_buckets(budgets)

    out = []
    for b in budgets:
        label = bucket_map.get(b, "budget")
        best_fixed = _best_method_for_budget(rows, b, FIXED_METHODS)
        oracle = _best_method_for_budget(rows, b, ["oracle_frontier_upper_bound"])
        heuristic = _best_method_for_budget(rows, b, ADAPTIVE_HEURISTIC_METHODS)
        learned = _best_method_for_budget(rows, b, LEARNED_POLICY_CANDIDATES)

        if best_fixed:
            out.append(
                {
                    "budget_bucket": label,
                    "budget": b,
                    "method_role": "best_fixed_single_family_baseline",
                    "method": best_fixed["method"],
                    "accuracy": best_fixed["accuracy"],
                    "avg_actions": best_fixed["avg_actions"],
                    "gap_to_oracle": best_fixed.get("gap_to_oracle", ""),
                    "availability": "available",
                }
            )

        out.append(
            {
                "budget_bucket": label,
                "budget": b,
                "method_role": "uniform_allocation_baseline",
                "method": "not_available_in_canonical_outputs",
                "accuracy": "",
                "avg_actions": "",
                "gap_to_oracle": "",
                "availability": "missing",
            }
        )

        if heuristic:
            out.append(
                {
                    "budget_bucket": label,
                    "budget": b,
                    "method_role": "heuristic_allocation_baseline",
                    "method": heuristic["method"],
                    "accuracy": heuristic["accuracy"],
                    "avg_actions": heuristic["avg_actions"],
                    "gap_to_oracle": heuristic.get("gap_to_oracle", ""),
                    "availability": "available",
                }
            )

        out.append(
            {
                "budget_bucket": label,
                "budget": b,
                "method_role": "learned_allocation_policy",
                "method": learned["method"] if learned else "not_available_in_canonical_outputs",
                "accuracy": learned["accuracy"] if learned else "",
                "avg_actions": learned["avg_actions"] if learned else "",
                "gap_to_oracle": learned.get("gap_to_oracle", "") if learned else "",
                "availability": "available" if learned else "missing",
            }
        )

        if oracle:
            out.append(
                {
                    "budget_bucket": label,
                    "budget": b,
                    "method_role": "oracle_frontier",
                    "method": oracle["method"],
                    "accuracy": oracle["accuracy"],
                    "avg_actions": oracle["avg_actions"],
                    "gap_to_oracle": oracle.get("gap_to_oracle", "0.0"),
                    "availability": "available",
                }
            )

    write_csv(PAPER_TABLE_DIR / "main_frontier_comparison.csv", out)

    tex_rows = [
        [
            str(r["budget"]),
            r["method_role"],
            r["method"],
            (fmt(as_float(r["accuracy"])) if r["accuracy"] != "" else "--"),
            (fmt(as_float(r["gap_to_oracle"])) if r["gap_to_oracle"] != "" else "--"),
        ]
        for r in out
        if r["method_role"] in {"best_fixed_single_family_baseline", "heuristic_allocation_baseline", "oracle_frontier", "learned_allocation_policy"}
    ]
    write_tex_table(
        PAPER_TABLE_DIR / "main_frontier_comparison.tex",
        ["Budget", "Role", "Method", "Accuracy", "Gap"],
        tex_rows,
        caption="Main frontier comparison at representative budgets (missing rows are explicit).",
        label="tab:main_frontier_comparison",
    )
    return out


def build_oracle_headroom_summary(main_table: list[dict]) -> None:
    by_budget = {}
    for r in main_table:
        by_budget.setdefault(int(r["budget"]), []).append(r)

    rows = []
    for b, b_rows in sorted(by_budget.items()):
        oracle = next((r for r in b_rows if r["method_role"] == "oracle_frontier"), None)
        fixed = next((r for r in b_rows if r["method_role"] == "best_fixed_single_family_baseline"), None)
        heuristic = next((r for r in b_rows if r["method_role"] == "heuristic_allocation_baseline"), None)
        learned = next((r for r in b_rows if r["method_role"] == "learned_allocation_policy" and r["availability"] == "available"), None)
        if not oracle:
            continue
        oracle_acc = as_float(oracle["accuracy"])
        fixed_acc = as_float(fixed["accuracy"]) if fixed else 0.0
        heuristic_acc = as_float(heuristic["accuracy"]) if heuristic else 0.0
        learned_acc = as_float(learned["accuracy"]) if learned else 0.0
        rows.append(
            {
                "budget": b,
                "oracle_accuracy": fmt(oracle_acc),
                "best_fixed_accuracy": fmt(fixed_acc),
                "heuristic_accuracy": fmt(heuristic_acc),
                "learned_accuracy": (fmt(learned_acc) if learned else ""),
                "oracle_gain_over_best_fixed": fmt(oracle_acc - fixed_acc),
                "oracle_gain_over_heuristic": fmt(oracle_acc - heuristic_acc),
                "learned_to_oracle_ratio": (fmt(learned_acc / oracle_acc) if learned and oracle_acc > 0 else ""),
                "heuristic_to_oracle_ratio": (fmt(heuristic_acc / oracle_acc) if oracle_acc > 0 else ""),
            }
        )

    write_csv(PAPER_TABLE_DIR / "oracle_headroom_summary.csv", rows)


def build_anti_collapse_diagnostics(data: dict) -> list[dict]:
    per_example = data["full_per_example"]
    method_pool = sorted({r["method"] for r in per_example if r["method"] in FIXED_METHODS or r["method"].startswith("adaptive_min_expand_")})
    rows = allocation_diversity_from_oracle(per_example, method_pool)
    for r in rows:
        for k in [
            "allocation_entropy",
            "max_family_share",
            "family_coverage",
            "oracle_frontier_accuracy",
            "best_single_family_reference_accuracy",
        ]:
            r[k] = fmt(as_float(r[k]))
    write_csv(PAPER_TABLE_DIR / "anti_collapse_diagnostics.csv", rows)
    return rows


def build_allocation_ablations(data: dict) -> None:
    per_seed = data["full_per_seed"]
    candidate = [r for r in per_seed if r["method"].startswith("adaptive_min_expand_")]
    mean_by_method = {}
    for m in sorted({r["method"] for r in candidate}):
        vals = [as_float(r["accuracy"]) for r in candidate if r["method"] == m]
        mean_by_method[m] = mean(vals) if vals else 0.0

    ref = mean_by_method.get("adaptive_min_expand_1", 0.0)
    rows = []
    for m, acc in sorted(mean_by_method.items()):
        min_expand = m.split("_")[-1]
        rows.append(
            {
                "ablation_group": "anti_collapse_min_expand_guard",
                "variant": m,
                "setting": f"min_expansions_before_prune={min_expand}",
                "support_status": "available",
                "mean_accuracy": fmt(acc),
                "delta_vs_adaptive_min_expand_1": fmt(acc - ref),
                "notes": "Directly supported by canonical full-method comparison bundle.",
            }
        )

    rows.extend(
        [
            {
                "ablation_group": "budget_conditioning",
                "variant": "adaptive_budget_guarded",
                "setting": "budget_guard_prune_floor and budget-aware thresholds",
                "support_status": "available_in_imported_frontier_eval_only",
                "mean_accuracy": "",
                "delta_vs_adaptive_min_expand_1": "",
                "notes": "Present in imported_methodology_frontier_eval; not in full multi-dataset seed bundle.",
            },
            {
                "ablation_group": "family_aware_features",
                "variant": "explicit_family_feature_toggle",
                "setting": "not available",
                "support_status": "missing",
                "mean_accuracy": "",
                "delta_vs_adaptive_min_expand_1": "",
                "notes": "No canonical ablation artifact isolating family-feature toggle.",
            },
            {
                "ablation_group": "difficulty_aware_features",
                "variant": "hardness_signal_toggle",
                "setting": "not available",
                "support_status": "missing",
                "mean_accuracy": "",
                "delta_vs_adaptive_min_expand_1": "",
                "notes": "Only hard/easy reporting exists; no direct training-time feature ablation.",
            },
            {
                "ablation_group": "oracle_inspired_targets",
                "variant": "oracle_target_supervision_toggle",
                "setting": "not available",
                "support_status": "missing",
                "mean_accuracy": "",
                "delta_vs_adaptive_min_expand_1": "",
                "notes": "No canonical paper-grade toggle in current run bundles.",
            },
        ]
    )

    write_csv(PAPER_TABLE_DIR / "allocation_ablations.csv", rows)
    tex_rows = [
        [r["ablation_group"], r["variant"], (r["mean_accuracy"] or "--"), r["support_status"]]
        for r in rows
    ]
    write_tex_table(
        PAPER_TABLE_DIR / "allocation_ablations.tex",
        ["Group", "Variant", "Mean acc.", "Status"],
        tex_rows,
        caption="Allocation-relevant ablations and explicit coverage gaps.",
        label="tab:allocation_ablations",
    )


def build_robustness_sensitivity(data: dict) -> None:
    per_seed = data["full_per_seed"]
    target_methods = ["adaptive_min_expand_1", "adaptive_min_expand_2", "reasoning_beam2", "self_consistency_3"]
    rows = []
    keys = sorted({(r["dataset"], r["budget"], r["method"]) for r in per_seed if r["method"] in target_methods})
    for dataset, budget, method in keys:
        vals = [as_float(r["accuracy"]) for r in per_seed if r["dataset"] == dataset and r["budget"] == budget and r["method"] == method]
        if not vals:
            continue
        m = mean(vals)
        std = 0.0 if len(vals) == 1 else (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
        rows.append(
            {
                "dataset": dataset,
                "budget": int(budget),
                "method": method,
                "n_seeds": len(vals),
                "mean_accuracy": fmt(m),
                "std_accuracy": fmt(std),
                "min_accuracy": fmt(min(vals)),
                "max_accuracy": fmt(max(vals)),
                "range_accuracy": fmt(max(vals) - min(vals)),
            }
        )

    write_csv(PAPER_TABLE_DIR / "robustness_sensitivity.csv", rows)


def main() -> None:
    ensure_output_dirs()
    inputs = load_inputs()
    data = _load(inputs)

    build_task_controller_summary(data)
    main_table = build_main_frontier_comparison(data)
    build_oracle_headroom_summary(main_table)
    build_anti_collapse_diagnostics(data)
    build_allocation_ablations(data)
    build_robustness_sensitivity(data)


if __name__ == "__main__":
    main()
