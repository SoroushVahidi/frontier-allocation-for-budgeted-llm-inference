#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv")
    target_method = "Promoted (Strict-Coupled Tie-Aware, bridged)"
    filtered = [r for r in rows if r["method"] == target_method]
    if not filtered:
        target_method = sorted({r["method"] for r in rows})[0]
        filtered = [r for r in rows if r["method"] == target_method]

    by_budget = {}
    for r in filtered:
        b = int(r["budget"])
        by_budget.setdefault(b, {})[r["component"]] = float(r["component_share"])

    budgets = sorted(by_budget)
    exp = [by_budget[b].get("Expansion", 0.0) for b in budgets]
    ver = [by_budget[b].get("Verification", 0.0) for b in budgets]

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.stackplot(budgets, exp, ver, labels=["Expansion share", "Verification share"], alpha=0.9, colors=["#4daf4a", "#377eb8"])
    apply_axis_style(ax, "Figure 4: Allocation Composition", "Compute Budget", "Action Share")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.subplots_adjust(right=0.78)
    save_fig(fig, FIGURE_DIR / "figure4_allocation_composition.pdf", FIGURE_DIR / "figure4_allocation_composition.png")


if __name__ == "__main__":
    main()
