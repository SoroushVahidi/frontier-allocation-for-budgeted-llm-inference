#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import STYLE, method_sort_key


def plot_appendix_per_dataset_curves() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_per_dataset_frontier_curves.csv")
    datasets = sorted({r["dataset"] for r in rows})
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)

    for dataset in datasets:
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        drows = [r for r in rows if r["dataset"] == dataset]
        for method in methods:
            mrows = sorted([r for r in drows if r["method"] == method], key=lambda r: int(r["budget"]))
            if not mrows:
                continue
            ax.plot([int(r["budget"]) for r in mrows], [float(r["accuracy"]) for r in mrows], marker="o", lw=1.8, ms=4.5, label=method, color=method_color(method))
        ax.set_title(f"Appendix: Full Frontier Curves ({dataset})", fontsize=STYLE.title_size)
        ax.set_xlabel("Budget", fontsize=STYLE.label_size)
        ax.set_ylabel("Accuracy", fontsize=STYLE.label_size)
        ax.grid(True, alpha=STYLE.grid_alpha)
        ax.legend(fontsize=STYLE.legend_size - 1, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
        safe = dataset.replace("/", "_")
        save_fig(fig, FIGURE_DIR / f"appendix_per_dataset_frontier_{safe}.pdf", FIGURE_DIR / f"appendix_per_dataset_frontier_{safe}.png")


def plot_appendix_failure_slice() -> None:
    path = PLOT_DATA_DIR / "appendix_promoted_vs_adversary_failure_slices.csv"
    if not path.exists():
        return
    rows = load_csv(path)
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)

    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    x = range(len(methods))
    vals = []
    for m in methods:
        mrows = [r for r in rows if r["method"] == m]
        vals.append(sum(float(r["near_tie_forced_accuracy"]) for r in mrows) / max(1, len(mrows)))
    ax.bar(list(x), vals, color=[method_color(m) for m in methods])
    ax.set_xticks(list(x))
    ax.set_xticklabels(methods, rotation=25, ha="right", fontsize=STYLE.tick_size)
    ax.set_ylabel("Near-Tie Forced Accuracy", fontsize=STYLE.label_size)
    ax.set_title("Appendix: Promoted vs Adversary on Failure Slices", fontsize=STYLE.title_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    save_fig(fig, FIGURE_DIR / "appendix_promoted_vs_adversary_failure_slices.pdf", FIGURE_DIR / "appendix_promoted_vs_adversary_failure_slices.png")


def main() -> None:
    plot_appendix_per_dataset_curves()
    plot_appendix_failure_slice()


if __name__ == "__main__":
    main()
