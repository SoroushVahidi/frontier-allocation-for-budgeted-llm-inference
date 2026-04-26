#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import load_csv, save_fig
from paper_style import METHOD_COLORS, STYLE, manuscript_method_display_name


def main() -> None:
    rows = load_csv(PLOT_DATA_DIR / "appendix_a3_allocation_composition.csv")
    methods = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max"]
    display_methods = [manuscript_method_display_name(m) for m in methods]
    by_method: dict[str, dict[str, float]] = {m: {} for m in methods}
    for r in rows:
        method = r["method"]
        if method not in by_method:
            continue
        by_method[method][r["metric"]] = float(r["value"])

    missing: list[str] = []
    for m in methods:
        for metric in ("avg_actions", "avg_expansions", "avg_verifications"):
            if metric not in by_method[m]:
                missing.append(f"{m}:{metric}")
    if missing:
        raise ValueError(f"Missing A3 allocation metrics: {missing}")

    avg_actions = [by_method[m]["avg_actions"] for m in methods]
    avg_expansions = [by_method[m]["avg_expansions"] for m in methods]
    avg_verifications = [by_method[m]["avg_verifications"] for m in methods]
    verification_share_pct = [
        (v / a * 100.0) if a > 0 else 0.0 for a, v in zip(avg_actions, avg_verifications)
    ]
    x = np.arange(len(methods))
    bar_colors = [METHOD_COLORS.get(m, "#666666") for m in methods]

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(STYLE.width + 2.0, STYLE.height + 0.75))

    # Left panel: absolute action composition (stacked), with total-action marker.
    ax_left.bar(x, avg_expansions, label="Average expansions", color=bar_colors, edgecolor="#2f2f2f", linewidth=0.8)
    ax_left.bar(
        x,
        avg_verifications,
        bottom=avg_expansions,
        label="Average verifications",
        color="#f28e2b",
        edgecolor="#2f2f2f",
        linewidth=0.8,
    )
    ax_left.scatter(x, avg_actions, label="Average actions (total)", marker="D", s=20, color="#222222", zorder=4)
    ax_left.set_title("Absolute action mix", fontsize=STYLE.title_size - 1)
    ax_left.set_ylabel("Mean count per case (actions)", fontsize=STYLE.label_size)
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(display_methods, rotation=20, ha="right", fontsize=STYLE.tick_size)
    ax_left.grid(True, axis="y", alpha=STYLE.grid_alpha)
    for xi, total in zip(x, avg_actions):
        ax_left.text(xi, total + 0.07, f"{total:.2f}", ha="center", va="bottom", fontsize=STYLE.tick_size - 1)

    # Right panel: verification share to make small verification differences readable.
    ax_right.bar(x, verification_share_pct, color=bar_colors, edgecolor="#2f2f2f", linewidth=0.8)
    ax_right.set_title("Verification share of actions", fontsize=STYLE.title_size - 1)
    ax_right.set_ylabel("Verification share (%)", fontsize=STYLE.label_size)
    ax_right.set_xticks(x)
    ax_right.set_xticklabels(display_methods, rotation=20, ha="right", fontsize=STYLE.tick_size)
    ax_right.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ymax = max(10.0, max(verification_share_pct) * 1.35)
    ax_right.set_ylim(0.0, ymax)
    for xi, pct in zip(x, verification_share_pct):
        ax_right.text(xi, pct + 0.35, f"{pct:.1f}%", ha="center", va="bottom", fontsize=STYLE.tick_size - 1)

    fig.suptitle("Allocation mix under fixed budget on the matched manuscript-facing surface", fontsize=STYLE.title_size)
    fig.legend(
        frameon=False,
        fontsize=STYLE.legend_size,
        loc="upper center",
        ncols=3,
        bbox_to_anchor=(0.5, 1.01),
    )
    fig.subplots_adjust(bottom=0.27, top=0.82, wspace=0.30)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_figure_a3_allocation_composition.pdf",
        FIGURE_DIR / "appendix_figure_a3_allocation_composition.png",
    )


if __name__ == "__main__":
    main()
