#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig, sorted_methods
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv")
    methods = sorted_methods(rows)
    vals = [float(next(r["accuracy"] for r in rows if r["method"] == m)) for m in methods]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    ax.bar(methods, vals, color=[method_color(m) for m in methods])
    apply_axis_style(ax, "Figure 2: Strict-Phased Default Decision Accuracy", "Method", "Accuracy")
    ax.tick_params(axis="x", rotation=28)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.set_ylim(0.0, max(vals) + 0.08)
    save_fig(fig, FIGURE_DIR / "figure2_main_frontier.pdf", FIGURE_DIR / "figure2_main_frontier.png")


if __name__ == "__main__":
    main()
