#!/usr/bin/env python3
from __future__ import annotations

from paper_data_sources import (
    PLOT_DATA_DIR,
    aggregate_frontier_macro,
    load_budget_aware_per_budget,
    load_multidataset_frontier,
    write_csv,
)


def main() -> None:
    strict_rows = load_multidataset_frontier()
    macro = aggregate_frontier_macro(strict_rows)
    budget_rows = load_budget_aware_per_budget()

    fig2_rows = []
    for r in macro:
        fig2_rows.append(
            {
                "method": r["method"],
                "budget": 0,
                "accuracy": r["macro_accuracy"],
                "avg_actions": r["macro_avg_actions"],
                "n_datasets": r["n_datasets"],
                "metric": "accuracy",
                "aggregation": "strict_phased_broader_surface",
            }
        )

    fig3_rows = []
    for r in macro:
        fig3_rows.append(
            {
                "method": r["method"],
                "budget": 0,
                "oracle_gap": 1.0 - r["macro_accuracy"],
                "normalized_regret": 1.0 - r["macro_accuracy"],
                "n_datasets": r["n_datasets"],
                "aggregation": "strict_phased_broader_surface",
            }
        )

    fig7_rows = []
    for r in strict_rows:
        fig7_rows.append(
            {
                "dataset": r["dataset"],
                "method": r["method"],
                "budget": 0,
                "accuracy": float(r["accuracy"]),
                "absent_from_tree": int(float(r.get("absent_from_tree", "0"))),
                "present_not_selected": int(float(r.get("present_not_selected", "0"))),
            }
        )

    # Appendix: budget-aware formula sweeps (canonical follow-up surface).
    appendix_budget_rows = []
    for r in budget_rows:
        appendix_budget_rows.append(
            {
                "formula": str(r["formula"]),
                "formula_expr": str(r["formula_expr"]),
                "budget": int(r["budget"]),
                "accuracy": float(r["accuracy"]),
                "repeated_same_family_present": int(r["repeated_same_family_present"]),
                "avg_max_family_share": float(r["avg_max_family_share"]),
            }
        )

    write_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv", fig2_rows)
    write_csv(PLOT_DATA_DIR / "figure3_oracle_gap.csv", fig3_rows)
    write_csv(PLOT_DATA_DIR / "figure7_per_dataset_summary.csv", fig7_rows)

    # Appendix artifact now explicitly formula-focused.
    write_csv(PLOT_DATA_DIR / "appendix_per_dataset_frontier_curves.csv", appendix_budget_rows)


if __name__ == "__main__":
    main()
