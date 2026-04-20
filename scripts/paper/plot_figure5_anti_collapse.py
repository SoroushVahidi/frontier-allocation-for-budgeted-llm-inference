#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure5_anti_collapse.csv")
    methods = sorted({r["method"] for r in rows}, key=method_sort_key)[:4]
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2), sharex=True)

    for method in methods:
        mrows = sorted([r for r in rows if r["method"] == method], key=lambda r: int(r["budget"]))
        axes[0].plot([int(r["budget"]) for r in mrows], [float(r["allocation_entropy"]) for r in mrows], marker="o", lw=1.9, ms=4.5, label=method)
        axes[1].plot([int(r["budget"]) for r in mrows], [float(r["max_family_share"]) for r in mrows], marker="o", lw=1.9, ms=4.5, label=method)

    axes[0].set_title("Allocation Entropy", fontsize=STYLE.title_size)
    axes[0].set_xlabel("Compute Budget", fontsize=STYLE.label_size)
    axes[0].set_ylabel("Entropy", fontsize=STYLE.label_size)
    axes[0].grid(True, alpha=STYLE.grid_alpha)

    axes[1].set_title("Max Family Share", fontsize=STYLE.title_size)
    axes[1].set_xlabel("Compute Budget", fontsize=STYLE.label_size)
    axes[1].set_ylabel("Max Share", fontsize=STYLE.label_size)
    axes[1].grid(True, alpha=STYLE.grid_alpha)

    axes[1].legend(fontsize=STYLE.legend_size, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.suptitle("Figure 5: Anti-Collapse Diagnostics", fontsize=STYLE.title_size)
    fig.subplots_adjust(right=0.81, top=0.83)
    save_fig(fig, FIGURE_DIR / "figure5_anti_collapse.pdf", FIGURE_DIR / "figure5_anti_collapse.png")


if __name__ == "__main__":
    main()
