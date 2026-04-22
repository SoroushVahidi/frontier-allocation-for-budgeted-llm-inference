#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import apply_axis_style, load_csv, method_color, save_fig
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_a1_oracle_gap_regret.csv")
    preferred = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max", "external_tale_prompt_budgeting", "external_s1_budget_forcing"]
    methods_present = sorted({r["method"] for r in rows})
    methods = [m for m in preferred if m in methods_present] + [m for m in methods_present if m not in preferred]
    fig, ax = plt.subplots(figsize=(STYLE.width + 0.4, STYLE.height + 0.6))
    for method in methods:
        mrows = sorted([r for r in rows if r["method"] == method], key=lambda r: int(r["budget"]))
        ax.plot(
            [int(r["budget"]) for r in mrows],
            [float(r["mean_regret_vs_inhouse_oracle"]) for r in mrows],
            marker="o",
            linewidth=2.0,
            markersize=4.8,
            label=method,
            color=method_color(method),
        )
    apply_axis_style(
        ax,
        "Oracle gap / regret on matched manuscript surface",
        "Budget",
        "Mean regret vs in-house oracle",
    )
    ax.set_xticks([4, 6, 8])
    ax.legend(frameon=False, fontsize=STYLE.legend_size, loc="upper right")
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a1_oracle_gap_regret.pdf",
        FIGURE_DIR / "appendix_figure_a1_oracle_gap_regret.png",
    )


if __name__ == "__main__":
    main()
