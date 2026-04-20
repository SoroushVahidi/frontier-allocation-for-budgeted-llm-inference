#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure6_failure_decomposition.csv")
    # choose strongest adversaries by case count for readability
    rows = sorted(rows, key=lambda r: int(r["n_defeat_cases"]), reverse=True)[:8]

    labels = [r["comparison_adversary"] for r in rows]
    tree = [float(r["absent_from_tree_failure_rate"]) for r in rows]
    output = [float(r["present_in_tree_output_layer_failure_rate"]) for r in rows]

    fig, ax = plt.subplots(figsize=(9.6, 4.9))
    ax.bar(labels, tree, label="Absent-from-tree failures", color="#e41a1c")
    ax.bar(labels, output, bottom=tree, label="Present-in-tree / output-layer failures", color="#377eb8")

    ax.set_title("Figure 6: Failure Decomposition", fontsize=STYLE.title_size)
    ax.set_xlabel("Adversary Method", fontsize=STYLE.label_size)
    ax.set_ylabel("Failure Rate Share", fontsize=STYLE.label_size)
    ax.tick_params(axis="x", rotation=32, labelsize=STYLE.tick_size)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(frameon=False, fontsize=STYLE.legend_size, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.subplots_adjust(right=0.74, bottom=0.28)

    save_fig(fig, FIGURE_DIR / "figure6_failure_decomposition.pdf", FIGURE_DIR / "figure6_failure_decomposition.png")


if __name__ == "__main__":
    main()
