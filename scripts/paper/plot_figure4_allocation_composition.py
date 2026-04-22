#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure4_allocation_composition.csv")
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)
    avg_actions = []
    avg_expansions = []
    avg_verifications = []
    for m in methods:
        mrows = [r for r in rows if r["method"] == m]
        avg_actions.append(next(float(r["value"]) for r in mrows if r["metric"] == "avg_actions"))
        avg_expansions.append(next(float(r["value"]) for r in mrows if r["metric"] == "avg_expansions"))
        avg_verifications.append(next(float(r["value"]) for r in mrows if r["metric"] == "avg_verifications"))

    fig, ax = plt.subplots(figsize=(STYLE.width + 1.4, STYLE.height + 1.0))
    x = list(range(len(methods)))
    w = 0.23

    ax.bar([i - w for i in x], avg_actions, width=w, label="Avg actions", color="#4e79a7")
    ax.bar(x, avg_expansions, width=w, label="Avg expansions", color="#59a14f")
    ax.bar([i + w for i in x], avg_verifications, width=w, label="Avg verifications", color="#f28e2b")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=26, ha="right", fontsize=STYLE.tick_size)
    ax.set_xlabel("Method / formula", fontsize=STYLE.label_size)
    ax.set_ylabel("Mean count per case", fontsize=STYLE.label_size)
    ax.set_title("Action allocation composition", fontsize=STYLE.title_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(frameon=False, fontsize=STYLE.legend_size, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    fig.subplots_adjust(bottom=0.30)
    save_fig(fig, FIGURE_DIR / "figure4_allocation_composition.pdf", FIGURE_DIR / "figure4_allocation_composition.png")


if __name__ == "__main__":
    main()
