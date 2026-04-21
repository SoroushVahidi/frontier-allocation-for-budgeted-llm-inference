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
    show_methods = methods[:6]

    fig, axes = plt.subplots(1, len(datasets), figsize=(4.6 * len(datasets), 4.6), sharey=True)
    if len(datasets) == 1:
        axes = [axes]

    for ax, dataset in zip(axes, datasets):
        drows = [r for r in rows if r["dataset"] == dataset]
        vals = []
        for method in show_methods:
            mrows = [r for r in drows if r["method"] == method]
            vals.append(float(mrows[0]["accuracy"]) if mrows else 0.0)
        ax.bar(show_methods, vals, color=[method_color(m) for m in show_methods])
        ax.set_title(dataset, fontsize=STYLE.label_size)
        ax.set_xlabel("Method", fontsize=STYLE.label_size)
        ax.grid(True, alpha=STYLE.grid_alpha)
        ax.tick_params(axis="x", rotation=28)
        for label in ax.get_xticklabels():
            label.set_ha("right")

    axes[0].set_ylabel("Accuracy", fontsize=STYLE.label_size)
    fig.suptitle("Figure 7: Per-Dataset Accuracy on Strict-Phased Surface", fontsize=STYLE.title_size)
    fig.subplots_adjust(top=0.82, bottom=0.30)
    save_fig(fig, FIGURE_DIR / "figure7_per_dataset_summary.pdf", FIGURE_DIR / "figure7_per_dataset_summary.png")


if __name__ == "__main__":
    main()
