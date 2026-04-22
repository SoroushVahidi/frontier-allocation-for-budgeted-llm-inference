#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE, manuscript_method_display_name


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_a2_anti_collapse.csv")
    methods = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max"]
    display_methods = [manuscript_method_display_name(m) for m in methods]
    vals = [float(next(r["repeated_same_family_case_rate"] for r in rows if r["method"] == m)) for m in methods]
    fig, ax = plt.subplots(figsize=(STYLE.width, STYLE.height + 0.4))
    ax.bar(display_methods, vals, color=["#1b9e77", "#377eb8", "#984ea3"])
    ax.set_title("Anti-collapse diagnostic: repeated same-family case rate", fontsize=STYLE.title_size)
    ax.set_xlabel("Method", fontsize=STYLE.label_size)
    ax.set_ylabel("Repeated same-family case rate", fontsize=STYLE.label_size)
    ax.tick_params(axis="x", rotation=24, labelsize=STYLE.tick_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    fig.subplots_adjust(bottom=0.23)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a2_anti_collapse.pdf",
        FIGURE_DIR / "appendix_figure_a2_anti_collapse.png",
    )


if __name__ == "__main__":
    main()
