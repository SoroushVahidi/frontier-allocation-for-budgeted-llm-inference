#!/usr/bin/env python3
from __future__ import annotations

from paper_data_sources import PLOT_DATA_DIR, aggregate_frontier_macro, load_multidataset_frontier, write_csv


def main() -> None:
    frontier_rows = load_multidataset_frontier()
    macro = aggregate_frontier_macro(frontier_rows)

    fig2_rows = []
    for r in macro:
        fig2_rows.append(
            {
                "method": r["method"],
                "budget": r["budget"],
                "accuracy": r["macro_accuracy"],
                "avg_actions": r["macro_avg_actions"],
                "n_datasets": r["n_datasets"],
                "metric": "Accuracy",
                "aggregation": "macro_over_datasets",
            }
        )

    fig3_rows = []
    for r in macro:
        fig3_rows.append(
            {
                "method": r["method"],
                "budget": r["budget"],
                "oracle_gap": r["macro_gap_to_oracle"],
                "normalized_regret": r["macro_gap_to_oracle"],
                "n_datasets": r["n_datasets"],
                "aggregation": "macro_over_datasets",
            }
        )

    fig7_rows = []
    for r in frontier_rows:
        fig7_rows.append(
            {
                "dataset": r["dataset"],
                "method": r["method"],
                "budget": int(float(r["budget"])),
                "accuracy": float(r["accuracy"]),
                "gap_to_oracle": float(r["gap_to_oracle"]),
            }
        )

    write_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv", fig2_rows)
    write_csv(PLOT_DATA_DIR / "figure3_oracle_gap.csv", fig3_rows)
    write_csv(PLOT_DATA_DIR / "figure7_per_dataset_summary.csv", fig7_rows)

    # Appendix: full per-dataset curves duplicate with explicit appendix naming.
    write_csv(PLOT_DATA_DIR / "appendix_per_dataset_frontier_curves.csv", fig7_rows)


if __name__ == "__main__":
    main()
