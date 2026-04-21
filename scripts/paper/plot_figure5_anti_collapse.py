#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure5_anti_collapse.csv")
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)
    entropy = []
    max_share = []
    for method in methods:
        mrows = [r for r in rows if r["method"] == method]
        entropy.append(sum(float(r["allocation_entropy"]) for r in mrows) / max(1, len(mrows)))
        max_share.append(sum(float(r["max_family_share"]) for r in mrows) / max(1, len(mrows)))
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6), sharex=True)
    axes[0].bar(methods, entropy)
    axes[1].bar(methods, max_share)

    axes[0].set_title("Longest Same-Family Run (mean)", fontsize=STYLE.title_size)
    axes[0].set_xlabel("Formula / Method", fontsize=STYLE.label_size)
    axes[0].set_ylabel("Run length", fontsize=STYLE.label_size)
    axes[0].grid(True, alpha=STYLE.grid_alpha)

    axes[1].set_title("Max Family Share", fontsize=STYLE.title_size)
    axes[1].set_xlabel("Formula / Method", fontsize=STYLE.label_size)
    axes[1].set_ylabel("Max Share", fontsize=STYLE.label_size)
    axes[1].grid(True, alpha=STYLE.grid_alpha)
    for ax in axes:
        ax.tick_params(axis="x", rotation=28, labelsize=STYLE.tick_size)
        for label in ax.get_xticklabels():
            label.set_ha("right")
    fig.suptitle("Figure 5: Family-Collapse Diagnostics Across Cap Policies", fontsize=STYLE.title_size)
    fig.subplots_adjust(top=0.84, bottom=0.28)
    save_fig(fig, FIGURE_DIR / "figure5_anti_collapse.pdf", FIGURE_DIR / "figure5_anti_collapse.png")


if __name__ == "__main__":
    main()
