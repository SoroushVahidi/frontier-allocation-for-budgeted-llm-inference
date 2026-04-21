#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure6_failure_decomposition.csv")
    rows = sorted(rows, key=lambda r: method_sort_key(r["method"]))[:8]

    labels = [r["method"] for r in rows]
    tree = [float(r["absent_from_tree_failure_rate"]) for r in rows]
    selected_wrong = [float(r["present_in_tree_output_layer_failure_rate"]) for r in rows]

    fig, ax = plt.subplots(figsize=(STYLE.width + 0.8, STYLE.height + 0.7))
    ax.bar(labels, tree, label="Absent from tree", color="#e41a1c")
    ax.bar(
        labels,
        selected_wrong,
        bottom=tree,
        label="Present in tree but misselected",
        color="#377eb8",
    )

    ax.set_title("Failure decomposition by method", fontsize=STYLE.title_size)
    ax.set_xlabel("Method", fontsize=STYLE.label_size)
    ax.set_ylabel("Average failure count per dataset", fontsize=STYLE.label_size)
    ax.tick_params(axis="x", rotation=32, labelsize=STYLE.tick_size)
    for i, label in enumerate(ax.get_xticklabels()):
        label.set_ha("right")
        if labels[i] == "strict_gate1_cap_k6 (default)":
            label.set_fontweight("bold")
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(frameon=False, fontsize=STYLE.legend_size, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.subplots_adjust(right=0.74, bottom=0.28)

    save_fig(fig, FIGURE_DIR / "figure6_failure_decomposition.pdf", FIGURE_DIR / "figure6_failure_decomposition.png")


if __name__ == "__main__":
    main()
