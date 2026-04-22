#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import STYLE


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_a4_component_ablation.csv")
    order = [
        "full_strict_f3",
        "no_answer_support",
        "no_anti_collapse",
        "no_repeat_expansion_control",
        "no_output_repair",
        "upstream_only_core",
        "strongest_reduced_variant",
    ]
    rows = sorted(rows, key=lambda r: order.index(r["variant"]))
    labels = [r["variant"] for r in rows]
    vals = [float(r["accuracy"]) for r in rows]

    fig, ax = plt.subplots(figsize=(STYLE.width + 1.4, STYLE.height + 0.8))
    bars = ax.bar(labels, vals, color="#4e79a7")
    for idx, label in enumerate(labels):
        if label == "full_strict_f3":
            bars[idx].set_color("#1b9e77")
        if label == "strongest_reduced_variant":
            bars[idx].set_color("#984ea3")

    ax.set_title("Strict_f3 component ablation summary", fontsize=STYLE.title_size)
    ax.set_xlabel("Variant", fontsize=STYLE.label_size)
    ax.set_ylabel("Accuracy", fontsize=STYLE.label_size)
    ax.tick_params(axis="x", rotation=24, labelsize=STYLE.tick_size)
    for tick in ax.get_xticklabels():
        tick.set_ha("right")
    ax.set_ylim(0.54, 0.72)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    fig.subplots_adjust(bottom=0.33)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a4_component_ablation.pdf",
        FIGURE_DIR / "appendix_figure_a4_component_ablation.png",
    )


if __name__ == "__main__":
    main()
