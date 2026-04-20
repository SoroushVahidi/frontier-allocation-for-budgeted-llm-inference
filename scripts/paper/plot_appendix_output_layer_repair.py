#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR, REPO_ROOT, write_csv
from plot_helpers import save_fig
from paper_style import STYLE

SUMMARY_JSON = REPO_ROOT / "outputs" / "current_failure_output_layer_repair_20260420" / "summary.json"
STATUS_MD = REPO_ROOT / "docs" / "CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md"


def _load_repair_summary() -> dict[str, int]:
    if SUMMARY_JSON.exists():
        payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
        return {
            "total_input_cases": int(payload["total_input_cases"]),
            "targeted_cases": int(payload["targeted_cases"]),
            "resolved_by_repair": int(payload["resolved_by_repair"]),
        }

    text = STATUS_MD.read_text(encoding="utf-8")
    targeted_match = re.search(r"Verified target set size:\s*\*\*(\d+)\*\*", text)
    resolved_match = re.search(r"Resolved by repair:\s*\*\*(\d+)\s*/\s*(\d+)\*\*", text)
    total_match = re.search(r"fresh\s+(\d+)-case", text, flags=re.IGNORECASE)
    if not (targeted_match and resolved_match and total_match):
        raise RuntimeError("Could not parse repair counts from current status doc.")

    return {
        "total_input_cases": int(total_match.group(1)),
        "targeted_cases": int(targeted_match.group(1)),
        "resolved_by_repair": int(resolved_match.group(1)),
    }


def _build_rows(summary: dict[str, int]) -> list[dict[str, Any]]:
    total_cases = summary["total_input_cases"]
    targeted_cases = summary["targeted_cases"]
    resolved_cases = summary["resolved_by_repair"]
    unresolved_cases = max(total_cases - resolved_cases, 0)

    return [
        {
            "panel": "targeted_subset",
            "group": "Before repair",
            "count": 0,
            "total": targeted_cases,
            "rate": 0.0 if targeted_cases == 0 else 0.0,
            "measure": "correct_surface_predictions",
        },
        {
            "panel": "targeted_subset",
            "group": "After repair",
            "count": resolved_cases,
            "total": targeted_cases,
            "rate": 0.0 if targeted_cases == 0 else resolved_cases / targeted_cases,
            "measure": "correct_surface_predictions",
        },
        {
            "panel": "full_failure_slice_after_repair",
            "group": "Recovered by deterministic repair",
            "count": resolved_cases,
            "total": total_cases,
            "rate": 0.0 if total_cases == 0 else resolved_cases / total_cases,
            "measure": "case_count",
        },
        {
            "panel": "full_failure_slice_after_repair",
            "group": "Still unresolved (upstream/tree-generation bottleneck)",
            "count": unresolved_cases,
            "total": total_cases,
            "rate": 0.0 if total_cases == 0 else unresolved_cases / total_cases,
            "measure": "case_count",
        },
    ]


def main() -> None:
    summary = _load_repair_summary()
    rows = _build_rows(summary)
    write_csv(PLOT_DATA_DIR / "appendix_output_layer_repair.csv", rows)

    targeted_rows = [r for r in rows if r["panel"] == "targeted_subset"]
    targeted_total = int(targeted_rows[0]["total"])
    targeted_before = int(next(r["count"] for r in targeted_rows if r["group"] == "Before repair"))
    targeted_after = int(next(r["count"] for r in targeted_rows if r["group"] == "After repair"))

    full_rows = [r for r in rows if r["panel"] == "full_failure_slice_after_repair"]
    recovered = int(next(r["count"] for r in full_rows if r["group"] == "Recovered by deterministic repair"))
    unresolved = int(next(r["count"] for r in full_rows if r["group"].startswith("Still unresolved")))
    total_cases = int(full_rows[0]["total"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.2))

    left_labels = ["Before repair", "After repair"]
    left_vals = [targeted_before, targeted_after]
    left_colors = ["#e41a1c", "#1b9e77"]
    bars = ax1.bar(left_labels, left_vals, color=left_colors, width=0.62)
    ax1.set_title("Targeted subset (correct reasoning already present)", fontsize=STYLE.label_size)
    ax1.set_ylabel("Correct surfaced cases", fontsize=STYLE.label_size)
    ax1.set_ylim(0, max(targeted_total, targeted_after) + 1.2)
    ax1.grid(True, axis="y", alpha=STYLE.grid_alpha)
    ax1.tick_params(axis="x", labelsize=STYLE.tick_size)
    ax1.tick_params(axis="y", labelsize=STYLE.tick_size)
    for bar, val in zip(bars, left_vals):
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.15,
            f"{val}/{targeted_total}",
            ha="center",
            va="bottom",
            fontsize=STYLE.tick_size,
        )

    y_label = "Current 20-case failure slice"
    ax2.barh([y_label], [recovered], color="#1b9e77", height=0.55)
    ax2.barh([y_label], [unresolved], left=[recovered], color="#d95f02", height=0.55)
    ax2.set_title("Bounded effect on the full failure slice", fontsize=STYLE.label_size)
    ax2.set_xlabel("Cases", fontsize=STYLE.label_size)
    ax2.set_xlim(0, total_cases)
    ax2.grid(True, axis="x", alpha=STYLE.grid_alpha)
    ax2.tick_params(axis="x", labelsize=STYLE.tick_size)
    ax2.tick_params(axis="y", labelsize=STYLE.tick_size)
    if recovered > 0:
        ax2.text(recovered / 2.0, 0, f"Recovered\n{recovered}", ha="center", va="center", fontsize=STYLE.tick_size, color="white")
    if unresolved > 0:
        ax2.text(recovered + unresolved / 2.0, 0, f"Unresolved\n{unresolved}", ha="center", va="center", fontsize=STYLE.tick_size, color="white")

    fig.suptitle("Appendix: Output-Layer Repair Effect", fontsize=STYLE.title_size)
    fig.subplots_adjust(bottom=0.22, wspace=0.4, top=0.84)
    save_fig(
        fig,
        FIGURE_DIR / "appendix_output_layer_repair.pdf",
        FIGURE_DIR / "appendix_output_layer_repair.png",
    )


if __name__ == "__main__":
    main()
