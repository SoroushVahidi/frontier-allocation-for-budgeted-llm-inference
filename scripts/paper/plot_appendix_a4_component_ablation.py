#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

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
    label_map = {
        "full_strict_f3": "Full Strict-F3 (baseline)",
        "no_answer_support": "Remove answer-support aggregation",
        "no_anti_collapse": "Remove anti-collapse allocation",
        "no_repeat_expansion_control": "Remove repeat-expansion control",
        "no_output_repair": "Remove output-layer repair",
        "upstream_only_core": "Reduced variant: upstream-only control stack",
        "strongest_reduced_variant": "Reduced variant: strongest reduced stack",
    }
    labels = [label_map.get(r["variant"], r["variant"]) for r in rows]
    deltas_pp = [float(r["delta_accuracy_vs_full"]) * 100.0 for r in rows]
    accuracies = [float(r["accuracy"]) for r in rows]
    variants = [r["variant"] for r in rows]

    # Visual grouping: baseline (green), component-removal ablations (neutral), reduced variants (purple).
    def _color_for_variant(variant: str) -> str:
        if variant == "full_strict_f3":
            return "#1b9e77"
        if variant in {"upstream_only_core", "strongest_reduced_variant"}:
            return "#9467bd"
        return "#8c9aa9"

    colors = [_color_for_variant(v) for v in variants]

    fig, ax = plt.subplots(figsize=(STYLE.width + 2.4, STYLE.height + 1.2))
    y = list(range(len(rows)))
    ax.barh(y, deltas_pp, color=colors, edgecolor="#2f2f2f", linewidth=0.8)
    ax.axvline(0.0, color="#222222", linewidth=1.0, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=STYLE.tick_size)
    ax.invert_yaxis()
    ax.set_xlabel("Accuracy delta vs Full Strict-F3 (percentage points)", fontsize=STYLE.label_size)
    ax.set_ylabel("Ablation variant", fontsize=STYLE.label_size)
    ax.set_title("Strict-F3 component ablations on the matched manuscript-facing surface", fontsize=STYLE.title_size)
    ax.grid(True, axis="x", alpha=STYLE.grid_alpha)

    for yi, (delta_pp, acc) in enumerate(zip(deltas_pp, accuracies)):
        pad = 0.35 if delta_pp >= 0 else -0.35
        ha = "left" if delta_pp >= 0 else "right"
        ax.text(delta_pp + pad, yi, f"{delta_pp:+.2f} pp (acc={acc:.3f})", va="center", ha=ha, fontsize=STYLE.tick_size - 1)

    ax.legend(
        handles=[
            Patch(facecolor="#1b9e77", edgecolor="#2f2f2f", label="Full method"),
            Patch(facecolor="#8c9aa9", edgecolor="#2f2f2f", label="Component-removal ablations"),
            Patch(facecolor="#9467bd", edgecolor="#2f2f2f", label="Reduced variants"),
        ],
        frameon=False,
        fontsize=STYLE.legend_size,
        loc="lower right",
    )

    max_abs = max(abs(v) for v in deltas_pp) if deltas_pp else 1.0
    lim = max(5.5, max_abs + 1.6)
    ax.set_xlim(-lim, lim)
    fig.subplots_adjust(left=0.40, right=0.97, top=0.88, bottom=0.16)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a4_component_ablation.pdf",
        FIGURE_DIR / "appendix_figure_a4_component_ablation.png",
    )


if __name__ == "__main__":
    main()
