#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from paper_data_sources import PLOT_DATA_DIR, REPO_ROOT, read_csv, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Build appendix-only extended-budget frontier plot data.")
    parser.add_argument(
        "--extended-bundle-dir",
        required=True,
        help="Path relative to repo root, e.g. outputs/extended_budget_frontier_<run_id>",
    )
    args = parser.parse_args()

    bundle_dir = REPO_ROOT / args.extended_bundle_dir
    frontier_csv = bundle_dir / "budget_performance_frontier.csv"
    ranking_csv = bundle_dir / "method_ranking_by_budget.csv"
    h2h_csv = bundle_dir / "head_to_head_summary.csv"

    frontier_rows = read_csv(frontier_csv)
    out_frontier = []
    for row in frontier_rows:
        out_frontier.append(
            {
                "budget": int(row["budget"]),
                "method": row["method"],
                "method_class": row["method_class"],
                "accuracy": float(row["mean_accuracy"]),
                "avg_actions": float(row["avg_actions"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_extended_budget_frontier.csv", out_frontier)

    ranking_rows = read_csv(ranking_csv)
    out_ranking = []
    for row in ranking_rows:
        out_ranking.append(
            {
                "budget": int(row["budget"]),
                "rank": int(row["rank"]),
                "method": row["method"],
                "method_class": row["method_class"],
                "accuracy": float(row["mean_accuracy"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_extended_budget_method_ranking.csv", out_ranking)

    h2h_rows = read_csv(h2h_csv)
    out_h2h = []
    for row in h2h_rows:
        out_h2h.append(
            {
                "budget": int(row["budget"]),
                "strict_f3_accuracy": float(row["strict_f3_accuracy"]),
                "strict_gate1_cap_k6_accuracy": float(row["strict_gate1_cap_k6_accuracy"]),
                "delta_strict_f3_minus_strict_gate1_cap_k6": float(row["delta_strict_f3_minus_strict_gate1_cap_k6"]),
                "best_near_direct_external": row["best_near_direct_external"],
                "best_near_direct_external_accuracy": float(row["best_near_direct_external_accuracy"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_extended_budget_head_to_head.csv", out_h2h)


if __name__ == "__main__":
    main()
