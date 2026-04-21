#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

from paper_data_sources import (
    PLOT_DATA_DIR,
    load_budget_aware_overall_table,
    load_canonical_hundred_aggregate,
    load_canonical_hundred_failure_table,
    load_multidataset_method_metrics,
    write_csv,
)


def build_allocation_composition() -> None:
    rows = load_multidataset_method_metrics()
    out = []
    for r in rows:
        avg_actions = float(r["avg_actions"])
        avg_exp = float(r["avg_expansions"])
        avg_ver = float(r["avg_verifications"])
        exp_share = (avg_exp / avg_actions) if avg_actions > 0 else 0.0
        ver_share = (avg_ver / avg_actions) if avg_actions > 0 else 0.0

        out.append(
            {
                "dataset": r["dataset"],
                "budget": int(float(r["budget"])),
                "method": r["method"],
                "component": "Expansion",
                "component_share": exp_share,
                "avg_component_actions": avg_exp,
                "avg_actions": avg_actions,
            }
        )
        out.append(
            {
                "dataset": r["dataset"],
                "budget": int(float(r["budget"])),
                "method": r["method"],
                "component": "Verification",
                "component_share": ver_share,
                "avg_component_actions": avg_ver,
                "avg_actions": avg_actions,
            }
        )

    write_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv", out)


def build_anti_collapse_diagnostics() -> None:
    rows = load_budget_aware_overall_table()
    out = []
    for r in rows:
        out.append(
            {
                "method": str(r["formula"]),
                "budget": int(r.get("budget", 0)),
                "accuracy": float(r["accuracy"]),
                "allocation_entropy": float(r["avg_longest_same_family_run"]),
                "max_family_share": float(r["avg_max_family_share"]),
                "repeated_same_family_present": int(r["repeated_same_family_present"]),
            }
        )

    write_csv(PLOT_DATA_DIR / "figure5_anti_collapse.csv", out)


def build_failure_decomposition() -> None:
    agg_json = load_canonical_hundred_aggregate()
    per_case = load_canonical_hundred_failure_table()
    by_dataset: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "tree": 0.0, "selection": 0.0})
    for r in per_case:
        ds = str(r["dataset"])
        by_dataset[ds]["n"] += 1.0
        if str(r["failure_type"]) == "absent_from_tree":
            by_dataset[ds]["tree"] += 1.0
        elif str(r["failure_type"]) == "present_not_selected":
            by_dataset[ds]["selection"] += 1.0
    out = []
    for dataset, stats in sorted(by_dataset.items()):
        n = max(1.0, stats["n"])
        out.append(
            {
                "dataset": dataset,
                "comparison_adversary": "reasoning_beam2",
                "absent_from_tree_failure_rate": stats["tree"] / n,
                "present_in_tree_output_layer_failure_rate": stats["selection"] / n,
                "other_failure_rate": 0.0,
                "n_defeat_cases": int(stats["n"]),
                "decomposition_basis": "canonical_hundred_failure_type",
            }
        )
    out.append(
        {
            "dataset": "ALL",
            "comparison_adversary": "reasoning_beam2",
            "absent_from_tree_failure_rate": float(agg_json["failure_type_counts"]["absent_from_tree"]["pct"]) / 100.0,
            "present_in_tree_output_layer_failure_rate": float(agg_json["failure_type_counts"]["present_not_selected"]["pct"]) / 100.0,
            "other_failure_rate": 0.0,
            "n_defeat_cases": int(agg_json["target_n"]),
            "decomposition_basis": "canonical_hundred_failure_type",
        }
    )

    write_csv(PLOT_DATA_DIR / "figure6_failure_decomposition.csv", out)


if __name__ == "__main__":
    build_allocation_composition()
    build_anti_collapse_diagnostics()
    build_failure_decomposition()
