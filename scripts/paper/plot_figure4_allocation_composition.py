#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv")
    methods = sorted({r["method"] for r in rows})
    exp = []
    ver = []
    for m in methods:
        mrows = [r for r in rows if r["method"] == m]
        exp.append(sum(float(r["component_share"]) for r in mrows if r["component"] == "Expansion") / max(1, len(mrows)))
        ver.append(sum(float(r["component_share"]) for r in mrows if r["component"] == "Verification") / max(1, len(mrows)))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.bar(methods, exp, label="Expansion share", color="#4daf4a")
    ax.bar(methods, ver, bottom=exp, label="Verification share", color="#377eb8")
    apply_axis_style(ax, "Figure 4: Strict-Phased Allocation Composition", "Method", "Action Share")
    ax.tick_params(axis="x", rotation=28)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.legend(frameon=False, loc="upper right")
    save_fig(fig, FIGURE_DIR / "figure4_allocation_composition.pdf", FIGURE_DIR / "figure4_allocation_composition.png")


if __name__ == "__main__":
    main()
