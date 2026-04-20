#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import CANONICAL_DATASET_ORDER, STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure7_per_dataset_summary.csv")
    datasets = [d for d in CANONICAL_DATASET_ORDER if d in {r['dataset'] for r in rows}]
    if not datasets:
        datasets = sorted({r["dataset"] for r in rows})

    methods = sorted({r["method"] for r in rows}, key=method_sort_key)
    show_methods = methods[:5]  # keep main figure readable

    fig, axes = plt.subplots(1, len(datasets), figsize=(4.8 * len(datasets), 4.4), sharey=True)
    if len(datasets) == 1:
        axes = [axes]

    for ax, dataset in zip(axes, datasets):
        drows = [r for r in rows if r["dataset"] == dataset]
        for method in show_methods:
            mrows = sorted([r for r in drows if r["method"] == method], key=lambda r: int(r["budget"]))
            if not mrows:
                continue
            ax.plot(
                [int(r["budget"]) for r in mrows],
                [float(r["accuracy"]) for r in mrows],
                marker="o",
                lw=1.8,
                ms=4.5,
                label=method,
                color=method_color(method),
            )
        ax.set_title(dataset, fontsize=STYLE.label_size)
        ax.set_xlabel("Budget", fontsize=STYLE.label_size)
        ax.grid(True, alpha=STYLE.grid_alpha)

    axes[0].set_ylabel("Accuracy", fontsize=STYLE.label_size)
    axes[-1].legend(fontsize=STYLE.legend_size - 1, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.suptitle("Figure 7: Per-Dataset Frontier Summary", fontsize=STYLE.title_size)
    fig.subplots_adjust(right=0.82, top=0.82)
    save_fig(fig, FIGURE_DIR / "figure7_per_dataset_summary.pdf", FIGURE_DIR / "figure7_per_dataset_summary.png")


if __name__ == "__main__":
    main()
