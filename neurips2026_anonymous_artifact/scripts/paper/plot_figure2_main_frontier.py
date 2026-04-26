#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig
from paper_style import STYLE, manuscript_method_display_name


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv")
    preferred = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max", "external_tale_prompt_budgeting", "external_s1_budget_forcing"]
    methods_present = sorted({r["method"] for r in rows})
    methods = [m for m in preferred if m in methods_present] + [m for m in methods_present if m not in preferred]
    fig, ax = plt.subplots(figsize=(STYLE.width + 0.4, STYLE.height + 0.6))
    for method in methods:
        mrows = sorted([r for r in rows if r["method"] == method], key=lambda r: int(r["budget"]))
        ax.plot(
            [int(r["budget"]) for r in mrows],
            [float(r["accuracy"]) for r in mrows],
            marker="o",
            linewidth=2.1,
            markersize=4.8,
            label=manuscript_method_display_name(method),
            color=method_color(method),
        )
    apply_axis_style(
        ax,
        "Budget-performance frontier on matched manuscript surface",
        "Budget",
        "Mean accuracy",
    )
    ax.set_xticks([4, 6, 8])
    ax.set_ylim(0.35, 0.75)
    ax.legend(
        frameon=False,
        fontsize=STYLE.legend_size,
        ncols=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.22),
    )
    fig.subplots_adjust(top=0.80)
    save_fig(fig, FIGURE_DIR / "figure2_main_frontier.pdf", FIGURE_DIR / "figure2_main_frontier.png")


if __name__ == "__main__":
    main()
