#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import STYLE, method_sort_key


def plot_appendix_per_dataset_curves() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_per_dataset_frontier_curves.csv")
    formulas = sorted({r["formula"] for r in rows}, key=method_sort_key)
    fig, ax = plt.subplots(figsize=(STYLE.width + 1.0, STYLE.height + 0.5))
    for formula in formulas:
        frows = sorted([r for r in rows if r["formula"] == formula], key=lambda r: int(r["budget"]))
        if not frows:
            continue
        ax.plot(
            [int(r["budget"]) for r in frows],
            [float(r["accuracy"]) for r in frows],
            marker="o",
            lw=1.8,
            ms=4.5,
            label=formula,
            color=method_color(formula),
        )
    ax.set_title("Appendix: Budget-aware formula accuracy curves", fontsize=STYLE.title_size)
    ax.set_xlabel("Budget", fontsize=STYLE.label_size)
    ax.set_ylabel("Accuracy", fontsize=STYLE.label_size)
    ax.grid(True, alpha=STYLE.grid_alpha)
    ax.legend(fontsize=STYLE.legend_size - 1, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    save_fig(fig, FIGURE_DIR / "appendix_budget_formula_curves.pdf", FIGURE_DIR / "appendix_budget_formula_curves.png")


def main() -> None:
    plot_appendix_per_dataset_curves()


if __name__ == "__main__":
    main()
