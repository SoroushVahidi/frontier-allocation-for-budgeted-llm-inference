#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

from paper_data_sources import (
    PLOT_DATA_DIR,
    load_budget_aware_overall_table,
    load_multidataset_method_metrics,
    write_csv,
)


def build_allocation_composition() -> None:
    # Main-paper allocation composition: action mix by method/formula.
    rows = load_budget_aware_overall_table()
    out = []
    for r in rows:
        out.append(
            {
                "method": str(r["formula"]),
                "metric": "avg_actions",
                "value": float(r["avg_actions"]),
            }
        )
        out.append(
            {
                "method": str(r["formula"]),
                "metric": "avg_expansions",
                "value": float(r["avg_expansions"]),
            }
        )
        out.append(
            {
                "method": str(r["formula"]),
                "metric": "avg_verifications",
                "value": float(r["avg_verifications"]),
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
                "longest_same_family_run": float(r["avg_longest_same_family_run"]),
                "max_family_share": float(r["avg_max_family_share"]),
                "repeated_same_family_present": int(r["repeated_same_family_present"]),
            }
        )

    write_csv(PLOT_DATA_DIR / "figure5_anti_collapse.csv", out)


def build_failure_decomposition() -> None:
    # Method-level failure decomposition from current strict-phased canonical surface.
    rows = load_multidataset_method_metrics()
    by_method: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "tree": 0.0, "selection": 0.0})
    for r in rows:
        m = str(r["method"])
        by_method[m]["n"] += 1.0
        by_method[m]["tree"] += float(r.get("absent_from_tree", 0.0))
        by_method[m]["selection"] += float(r.get("present_not_selected", 0.0))
    out = []
    for method, stats in sorted(by_method.items()):
        n = max(1.0, stats["n"])
        out.append(
            {
                "method": method,
                "absent_from_tree_failure_rate": stats["tree"] / n,
                "present_in_tree_output_layer_failure_rate": stats["selection"] / n,
                "n_rows": int(stats["n"]),
                "decomposition_basis": "strict_phased_current_surface",
            }
        )

    write_csv(PLOT_DATA_DIR / "figure6_failure_decomposition.csv", out)


if __name__ == "__main__":
    build_allocation_composition()
    build_anti_collapse_diagnostics()
    build_failure_decomposition()
