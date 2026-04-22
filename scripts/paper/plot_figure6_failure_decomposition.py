#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure3_failure_decomposition.csv")
    order = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max"]
    rows = sorted(rows, key=lambda r: order.index(r["method"]))

    labels = [r["method"] for r in rows]
    tree = [float(r["absent_from_tree_rate"]) for r in rows]
    selected_wrong = [float(r["present_not_selected_rate"]) + float(r["output_layer_mismatch_rate"]) for r in rows]

    fig, ax = plt.subplots(figsize=(STYLE.width + 0.2, STYLE.height + 0.5))
    x = np.arange(len(labels))
    ax.bar(x, tree, label="Absent-from-tree", color="#e41a1c")
    ax.bar(
        x,
        selected_wrong,
        bottom=tree,
        label="Present-not-selected / output-layer",
        color="#377eb8",
    )

    ax.set_title("Failure decomposition on matched manuscript surface", fontsize=STYLE.title_size)
    ax.set_xlabel("Method", fontsize=STYLE.label_size)
    ax.set_ylabel("Failure rate", fontsize=STYLE.label_size)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=STYLE.tick_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(
        frameon=False,
        fontsize=STYLE.legend_size,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.17),
        ncols=2,
    )
    fig.subplots_adjust(bottom=0.30)

    save_fig(fig, FIGURE_DIR / "figure3_failure_decomposition.pdf", FIGURE_DIR / "figure3_failure_decomposition.png")


if __name__ == "__main__":
    main()
