#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR, REPO_ROOT, write_csv
from plot_helpers import save_fig
from paper_style import STYLE

SUMMARY_JSON = REPO_ROOT / "outputs" / "current_failure_output_layer_repair_20260420" / "summary.json"
MISMATCH_JSON = REPO_ROOT / "outputs" / "current_failure_output_layer_repair_20260420" / "mismatch_breakdown.json"


def _load_repair_summary() -> dict[str, int]:
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    mismatch = json.loads(MISMATCH_JSON.read_text(encoding="utf-8"))
    return {
        "targeted_cases": int(payload["targeted_cases"]),
        "resolved_by_repair": int(payload["resolved_by_repair"]),
        "unresolved_after_repair": int(mismatch["unresolved_after_repair"]),
    }


def _build_rows(summary: dict[str, int]) -> list[dict[str, Any]]:
    targeted_cases = summary["targeted_cases"]
    resolved_cases = summary["resolved_by_repair"]
    unresolved_cases = summary["unresolved_after_repair"]
    incorrect_before = targeted_cases

    return [
        {
            "metric": "Targeted subset size",
            "count": targeted_cases,
            "total": targeted_cases,
            "rate": 1.0,
        },
        {
            "metric": "Incorrect before repair",
            "count": incorrect_before,
            "total": targeted_cases,
            "rate": 0.0 if targeted_cases == 0 else incorrect_before / targeted_cases,
        },
        {
            "metric": "Correct after repair",
            "count": resolved_cases,
            "total": targeted_cases,
            "rate": 0.0 if targeted_cases == 0 else resolved_cases / targeted_cases,
        },
        {
            "metric": "Unresolved after repair",
            "count": unresolved_cases,
            "total": targeted_cases,
            "rate": 0.0 if targeted_cases == 0 else unresolved_cases / targeted_cases,
        },
    ]


def main() -> None:
    summary = _load_repair_summary()
    rows = _build_rows(summary)
    write_csv(PLOT_DATA_DIR / "appendix_output_layer_repair.csv", rows)

    labels = [r["metric"] for r in rows]
    values = [int(r["count"]) for r in rows]
    totals = [int(r["total"]) for r in rows]
    colors = ["#7570b3", "#e41a1c", "#1b9e77", "#d95f02"]

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    bars = ax.bar(labels, values, color=colors, width=0.64)
    ax.set_title("Appendix: Output-Layer Repair on Targeted In-Tree Subset", fontsize=STYLE.title_size)
    ax.set_ylabel("Case count", fontsize=STYLE.label_size)
    ax.set_ylim(0, max(values) + 1.6)
    ax.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax.tick_params(axis="x", rotation=18, labelsize=STYLE.tick_size)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.tick_params(axis="y", labelsize=STYLE.tick_size)

    for bar, val, total in zip(bars, values, totals):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.15,
            f"{val}/{total}",
            ha="center",
            va="bottom",
            fontsize=STYLE.tick_size,
        )

    ax.text(
        0.01,
        0.98,
        "Subset definition: current method wrong, self-consistency correct,\nand correct answer already present in the tree.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=STYLE.tick_size - 1,
        color="#333333",
    )

    fig.subplots_adjust(bottom=0.28, top=0.86)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_output_layer_repair.pdf",
        FIGURE_DIR / "appendix_output_layer_repair.png",
    )


if __name__ == "__main__":
    main()
