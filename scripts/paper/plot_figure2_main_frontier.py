#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig, sorted_methods
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv")
    methods = sorted_methods(rows)
    vals = [float(next(r["accuracy"] for r in rows if r["method"] == m)) for m in methods]
    fig, ax = plt.subplots(figsize=(STYLE.width, STYLE.height + 0.7))
    bars = ax.bar(methods, vals, color=[method_color(m) for m in methods])
    apply_axis_style(
        ax,
        "Strict-phased main method comparison",
        "Method",
        "Macro accuracy",
    )
    ax.tick_params(axis="x", rotation=26)
    for idx, label in enumerate(ax.get_xticklabels()):
        label.set_ha("right")
        # Bold current default and strongest competitor for visual focus.
        if methods[idx] == "strict_gate1_cap_k6 (default)" or vals[idx] == max(vals):
            label.set_fontweight("bold")
            bars[idx].set_edgecolor("#111111")
            bars[idx].set_linewidth(1.2)
    ax.set_ylim(0.0, max(vals) + 0.08)
    save_fig(fig, FIGURE_DIR / "figure2_main_frontier.pdf", FIGURE_DIR / "figure2_main_frontier.png")


if __name__ == "__main__":
    main()
