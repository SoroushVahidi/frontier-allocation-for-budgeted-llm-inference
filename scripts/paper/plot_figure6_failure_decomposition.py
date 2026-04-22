#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR, REPO_ROOT, read_csv
from plot_helpers import load_csv, save_fig
from paper_style import STYLE


def _plot(rows: list[dict[str, str]], out_pdf: str, out_png: str, title: str, note: str) -> None:
    labels = [r["method"] for r in rows]
    labels = ["external_l1_max*" if m == "external_l1_max" else m for m in labels]
    absent = [float(r["absent_from_tree_rate"]) for r in rows]
    present_not_selected = [float(r["present_not_selected_rate"]) + float(r["output_layer_mismatch_rate"]) for r in rows]

    fig, ax = plt.subplots(figsize=(STYLE.width + 1.2, STYLE.height + 0.8))
    x = np.arange(len(labels))
    ax.bar(x, absent, label="Absent-from-tree", color="#e41a1c")
    ax.bar(
        x,
        present_not_selected,
        bottom=absent,
        label="Present-not-selected",
        color="#377eb8",
    )

    ax.set_title(title, fontsize=STYLE.title_size)
    ax.set_xlabel("Method", fontsize=STYLE.label_size, labelpad=12)
    ax.set_ylabel("Failure rate", fontsize=STYLE.label_size)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right", fontsize=STYLE.tick_size)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.legend(  # keep legend outside to avoid bar/title overlap
        frameon=False,
        fontsize=STYLE.legend_size,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )

    # Annotate stacked totals and present-not-selected segment values.
    for i, (a, p) in enumerate(zip(absent, present_not_selected)):
        total = a + p
        ax.text(i, total + 0.009, f"{total:.3f}", ha="center", va="bottom", fontsize=STYLE.tick_size - 1, color="#333333")
        if p > 0:
            ax.text(
                i,
                a + p / 2.0,
                f"{p:.3f}",
                ha="center",
                va="center",
                fontsize=STYLE.tick_size - 1,
                color="white",
            )

    ax.set_ylim(0.0, max(a + p for a, p in zip(absent, present_not_selected)) + 0.06)
    fig.subplots_adjust(right=0.76, bottom=0.34)
    fig.text(0.01, 0.008, note, ha="left", va="bottom", fontsize=STYLE.tick_size - 2, color="#333333")

    save_fig(fig, FIGURE_DIR / out_pdf, FIGURE_DIR / out_png)


def main() -> None:
    main_rows = load_csv(PLOT_DATA_DIR / "figure3_failure_decomposition.csv")
    main_order = ["strict_f3", "strict_gate1_cap_k6", "external_l1_max"]
    main_rows = sorted(main_rows, key=lambda r: main_order.index(r["method"]))

    _plot(
        main_rows,
        "figure3_failure_decomposition.pdf",
        "figure3_failure_decomposition.png",
        "Failure decomposition on matched manuscript surface",
        "* external_l1_max is the strongest fair near-direct external baseline on the locked decision surface.",
    )

    # Optional appendix-expanded view with all fair near-direct externals.
    source_rows = read_csv(
        REPO_ROOT
        / "outputs"
        / "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3"
        / "20260422T175142Z"
        / "failure_decomposition.csv"
    )
    appendix_order = [
        "strict_f3",
        "strict_gate1_cap_k6",
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
        "external_l1_exact",
    ]
    source_rows = [r for r in source_rows if r["method"] in appendix_order]
    source_rows = sorted(source_rows, key=lambda r: appendix_order.index(r["method"]))
    _plot(
        source_rows,
        "figure3_failure_decomposition_all_externals_appendix.pdf",
        "figure3_failure_decomposition_all_externals_appendix.png",
        "Failure decomposition (expanded fair near-direct externals)",
        "* external_l1_max remains the strongest fair near-direct external baseline; others shown for appendix completeness.",
    )


if __name__ == "__main__":
    main()
