#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, method_color, save_fig
from paper_style import CANONICAL_DATASET_ORDER, STYLE, method_sort_key


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "figure7_per_dataset_summary.csv")
    datasets = [d for d in CANONICAL_DATASET_ORDER if d in {r['dataset'] for r in rows}]
    if not datasets:
        datasets = sorted({r["dataset"] for r in rows})

    methods = sorted({r["method"] for r in rows}, key=method_sort_key)
    preferred = [
        "strict_gate1_cap_k6 (default)",
        "strict_gate1",
        "strict_f2",
        "strict_f3",
        "strict_gate2",
        "baseline",
    ]
    show_methods = [m for m in preferred if m in methods] or methods[:6]

    short_ds = {
        "openai/gsm8k": "GSM8K",
        "HuggingFaceH4/MATH-500": "MATH-500",
        "olympiadbench": "OlympiadBench",
        "HuggingFaceH4/aime_2024": "AIME 2024",
    }

    x = np.arange(len(datasets))
    width = 0.12
    fig, ax = plt.subplots(figsize=(STYLE.width + 1.2, STYLE.height + 0.9))
    for i, method in enumerate(show_methods):
        vals = []
        for dataset in datasets:
            drows = [r for r in rows if r["dataset"] == dataset and r["method"] == method]
            vals.append(float(drows[0]["accuracy"]) if drows else 0.0)
        offset = (i - (len(show_methods) - 1) / 2.0) * width
        edge_lw = 1.0 if method == "strict_gate1_cap_k6 (default)" else 0.0
        ax.bar(
            x + offset,
            vals,
            width=width,
            label=method,
            color=method_color(method),
            edgecolor="#111111" if edge_lw > 0 else None,
            linewidth=edge_lw,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([short_ds.get(d, d) for d in datasets], fontsize=STYLE.tick_size)
    ax.set_ylabel("Accuracy", fontsize=STYLE.label_size)
    ax.set_xlabel("Dataset", fontsize=STYLE.label_size)
    ax.set_title("Per-dataset strict-phased summary", fontsize=STYLE.title_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(frameon=False, fontsize=STYLE.legend_size, ncols=2, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.subplots_adjust(bottom=0.30)
    save_fig(fig, FIGURE_DIR / "figure7_per_dataset_summary.pdf", FIGURE_DIR / "figure7_per_dataset_summary.png")


if __name__ == "__main__":
    main()
