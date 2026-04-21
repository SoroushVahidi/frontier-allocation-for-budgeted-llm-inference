#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig, sorted_methods
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure3_oracle_gap.csv")
    methods = sorted_methods(rows)
    vals = [float(next(r["oracle_gap"] for r in rows if r["method"] == m)) for m in methods]
    fig, ax = plt.subplots(figsize=(STYLE.width, STYLE.height + 0.6))
    ax.bar(methods, vals, color=[method_color(m) for m in methods])
    apply_axis_style(
        ax,
        "Residual error proxy on strict-phased surface",
        "Method",
        "Residual error (1 - macro accuracy)",
    )
    ax.tick_params(axis="x", rotation=28)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    save_fig(fig, FIGURE_DIR / "figure3_oracle_gap.pdf", FIGURE_DIR / "figure3_oracle_gap.png")


if __name__ == "__main__":
    main()
