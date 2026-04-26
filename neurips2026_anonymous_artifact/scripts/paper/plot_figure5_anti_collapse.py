#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import METHOD_COLORS, STYLE, manuscript_method_display_name


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_a2_anti_collapse.csv")
    methods = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max"]
    by_method = {r["method"]: r for r in rows}
    missing = [m for m in methods if m not in by_method]
    if missing:
        raise ValueError(f"Missing anti-collapse rows for required methods: {missing}")

    labels = [manuscript_method_display_name(m) for m in methods]
    repeated_rates = [float(by_method[m]["repeated_same_family_case_rate"]) for m in methods]
    avg_expansions = [float(by_method[m]["avg_expansions"]) for m in methods]
    colors = [METHOD_COLORS.get(m, "#666666") for m in methods]
    x = np.arange(len(methods))

    fig, axes = plt.subplots(1, 2, figsize=(STYLE.width + 1.5, STYLE.height + 0.55))
    ax_left, ax_right = axes

    # A2-left: anti-collapse concentration proxy.
    ax_left.bar(x, repeated_rates, color=colors, edgecolor="#2f2f2f", linewidth=0.8)
    ax_left.set_title("Repeated same-family case rate", fontsize=STYLE.title_size - 1)
    ax_left.set_xlabel("Method", fontsize=STYLE.label_size)
    ax_left.set_ylabel("Rate", fontsize=STYLE.label_size)
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(labels, rotation=24, ha="right", fontsize=STYLE.tick_size)
    ax_left.set_ylim(0.0, 1.0)
    ax_left.grid(True, axis="y", alpha=STYLE.grid_alpha)

    # Make zero-valued methods visibly present (the root cause of "missing bar" appearance).
    for xi, yi in zip(x, repeated_rates):
        if yi == 0.0:
            ax_left.scatter([xi], [0.0], marker="o", s=18, color="#2f2f2f", zorder=4)
            ax_left.text(xi, 0.02, "0.000", ha="center", va="bottom", fontsize=STYLE.tick_size - 1)
        else:
            ax_left.text(xi, yi + 0.015, f"{yi:.3f}", ha="center", va="bottom", fontsize=STYLE.tick_size - 1)

    # A2-right: context metric so external zero-rates are not misread.
    ax_right.bar(x, avg_expansions, color=colors, edgecolor="#2f2f2f", linewidth=0.8)
    ax_right.set_title("Average expansions per case", fontsize=STYLE.title_size - 1)
    ax_right.set_xlabel("Method", fontsize=STYLE.label_size)
    ax_right.set_ylabel("Mean expansions", fontsize=STYLE.label_size)
    ax_right.set_xticks(x)
    ax_right.set_xticklabels(labels, rotation=24, ha="right", fontsize=STYLE.tick_size)
    ax_right.grid(True, axis="y", alpha=STYLE.grid_alpha)
    for xi, yi in zip(x, avg_expansions):
        ax_right.text(xi, yi + 0.05, f"{yi:.2f}", ha="center", va="bottom", fontsize=STYLE.tick_size - 1)

    fig.suptitle("Appendix A2: anti-collapse diagnostic comparison", fontsize=STYLE.title_size)
    fig.subplots_adjust(bottom=0.30, wspace=0.28, top=0.84)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a2_anti_collapse.pdf",
        FIGURE_DIR / "appendix_figure_a2_anti_collapse.png",
    )


if __name__ == "__main__":
    main()
