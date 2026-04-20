#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

from paper_data_sources import (
    CANONICAL_FULL_BUNDLE,
    PLOT_DATA_DIR,
    load_multidataset_method_metrics,
    read_csv,
    to_float,
    to_int,
    write_csv,
)


def build_allocation_composition() -> None:
    rows = load_multidataset_method_metrics()
    out = []
    for r in rows:
        avg_actions = to_float(r["avg_actions"])
        avg_exp = to_float(r["avg_expansions"])
        avg_ver = to_float(r["avg_verifications"])
        exp_share = (avg_exp / avg_actions) if avg_actions > 0 else 0.0
        ver_share = (avg_ver / avg_actions) if avg_actions > 0 else 0.0

        out.append(
            {
                "dataset": r["dataset"],
                "budget": to_int(r["budget"]),
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
                "budget": to_int(r["budget"]),
                "method": r["method"],
                "component": "Verification",
                "component_share": ver_share,
                "avg_component_actions": avg_ver,
                "avg_actions": avg_actions,
            }
        )

    write_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv", out)


def build_anti_collapse_diagnostics() -> None:
    rows = load_multidataset_method_metrics()
    out = []
    for r in rows:
        avg_actions = to_float(r["avg_actions"])
        avg_exp = to_float(r["avg_expansions"])
        avg_ver = to_float(r["avg_verifications"])
        p_exp = (avg_exp / avg_actions) if avg_actions > 0 else 0.0
        p_ver = (avg_ver / avg_actions) if avg_actions > 0 else 0.0
        entropy = 0.0
        for p in (p_exp, p_ver):
            if p > 1e-12:
                from math import log

                entropy -= p * log(p)
        active_family_count = int(avg_exp > 0) + int(avg_ver > 0)
        max_family_share = max(p_exp, p_ver)
        monopolization_rate = 1.0 if max_family_share >= 0.95 else 0.0

        out.append(
            {
                "dataset": r["dataset"],
                "budget": to_int(r["budget"]),
                "method": r["method"],
                "accuracy": to_float(r["accuracy"]),
                "budget_exhaustion_rate": to_float(r["budget_exhaustion_rate"]),
                "allocation_entropy": entropy,
                "max_family_share": max_family_share,
                "active_family_count": active_family_count,
                "monopolization_rate": monopolization_rate,
            }
        )

    write_csv(PLOT_DATA_DIR / "figure5_anti_collapse.csv", out)


def build_failure_decomposition() -> None:
    defeat_rows = read_csv(CANONICAL_FULL_BUNDLE / "defeat_case_registry.csv")

    tree_like = {
        "under_exploration_or_early_commit",
        "branch_allocation_gap",
        "inefficient_budget_spend",
    }
    output_like = {"selection_or_aggregation_gap"}

    agg: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"n": 0.0, "tree": 0.0, "output": 0.0, "other": 0.0})
    for r in defeat_rows:
        key = (r["dataset"], r["other_method"])
        agg[key]["n"] += 1.0
        subtype = r.get("failure_subtype", "")
        if subtype in tree_like:
            agg[key]["tree"] += 1.0
        elif subtype in output_like:
            agg[key]["output"] += 1.0
        else:
            agg[key]["other"] += 1.0

    out = []
    for (dataset, adversary), stats in sorted(agg.items(), key=lambda x: x[0]):
        n = max(1.0, stats["n"])
        out.append(
            {
                "dataset": dataset,
                "comparison_adversary": adversary,
                "absent_from_tree_failure_rate": stats["tree"] / n,
                "present_in_tree_output_layer_failure_rate": stats["output"] / n,
                "other_failure_rate": stats["other"] / n,
                "n_defeat_cases": int(stats["n"]),
                "decomposition_basis": "defeat_case_failure_subtype_proxy",
            }
        )

    write_csv(PLOT_DATA_DIR / "figure6_failure_decomposition.csv", out)


if __name__ == "__main__":
    build_allocation_composition()
    build_anti_collapse_diagnostics()
    build_failure_decomposition()
