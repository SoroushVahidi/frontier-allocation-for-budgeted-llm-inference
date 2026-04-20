#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig, sorted_methods
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))

    for method in sorted_methods(rows):
        mrows = sorted([r for r in rows if r["method"] == method], key=lambda r: int(r["budget"]))
        ax.plot(
            [int(r["budget"]) for r in mrows],
            [float(r["accuracy"]) for r in mrows],
            label=method,
            lw=STYLE.line_width,
            marker="o",
            ms=STYLE.marker_size,
            color=method_color(method),
        )

    apply_axis_style(ax, "Figure 2: Main Budget-Performance Frontier", "Compute Budget", "Accuracy")
    ax.legend(fontsize=STYLE.legend_size, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.subplots_adjust(right=0.74)
    save_fig(fig, FIGURE_DIR / "figure2_main_frontier.pdf", FIGURE_DIR / "figure2_main_frontier.png")


if __name__ == "__main__":
    main()
