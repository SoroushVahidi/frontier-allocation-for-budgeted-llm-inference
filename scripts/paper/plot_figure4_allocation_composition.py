#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv")
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)
    max_share = []
    longest_run = []
    for m in methods:
        mrows = [r for r in rows if r["method"] == m]
        max_share.append(next(float(r["value"]) for r in mrows if r["metric"] == "max_family_share"))
        longest_run.append(next(float(r["value"]) for r in mrows if r["metric"] == "longest_same_family_run"))

    fig, axes = plt.subplots(1, 2, figsize=(STYLE.width + 1.2, STYLE.height + 0.6), sharex=True)
    axes[0].bar(methods, max_share, color=[method_color(m) for m in methods])
    axes[0].set_title("Max family share", fontsize=STYLE.title_size)
    axes[0].set_ylabel("Share", fontsize=STYLE.label_size)
    axes[0].grid(True, axis="y", alpha=STYLE.grid_alpha)

    axes[1].bar(methods, longest_run, color=[method_color(m) for m in methods])
    axes[1].set_title("Longest same-family run", fontsize=STYLE.title_size)
    axes[1].set_ylabel("Run length", fontsize=STYLE.label_size)
    axes[1].grid(True, axis="y", alpha=STYLE.grid_alpha)

    for ax in axes:
        ax.set_xlabel("Method", fontsize=STYLE.label_size)
        ax.tick_params(axis="x", rotation=26, labelsize=STYLE.tick_size)
        for label in ax.get_xticklabels():
            label.set_ha("right")
    save_fig(fig, FIGURE_DIR / "figure4_allocation_composition.pdf", FIGURE_DIR / "figure4_allocation_composition.png")


if __name__ == "__main__":
    main()
