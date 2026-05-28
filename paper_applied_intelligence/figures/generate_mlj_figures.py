from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = (
    ROOT
    / "outputs"
    / "machine_learning_journal_result_package_20260520_20260520T035127Z"
)
FIG_DIR = ROOT / "paper_ml_journal" / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_float(value: str) -> float:
    return float(value)


def save_fig(fig: plt.Figure, stem: str) -> None:
    pdf_path = FIG_DIR / f"{stem}.pdf"
    png_path = FIG_DIR / f"{stem}.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")


def make_accuracy_ci() -> None:
    rows = read_csv(DATA_DIR / "figure_data_accuracy_vs_baseline.csv")
    deltas = read_csv(DATA_DIR / "figure_data_delta_ci.csv")

    methods = ["frontier", "fix2", "fix24", "l1", "s1", "tale"]
    labels = {
        "frontier": "Frontier\noriginal",
        "fix2": "FIX-2",
        "fix24": "FIX-2+FIX-4",
        "l1": "L1",
        "s1": "S1",
        "tale": "TALE",
    }
    split_order = ["final300", "aggregate720"]
    split_label = {"final300": "Final-300", "aggregate720": "Aggregate-720"}
    palette = ["#4C78A8", "#F58518"]

    values: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        values[row["policy"]][row["split"]] = to_float(row["accuracy_pct"])

    delta_rows = {row["comparison"]: row for row in deltas if row["split"] == "aggregate720"}
    delta_labels = {
        "fix24_minus_l1": "L1",
        "fix24_minus_s1": "S1",
        "fix24_minus_tale": "TALE",
        "fix24_minus_best_external": "Best external",
    }

    fig, (ax1, ax2) = plt.subplots(
        1,
        2,
        figsize=(9.2, 4.2),
        constrained_layout=True,
    )

    x = np.arange(len(methods))
    width = 0.34
    for idx, split in enumerate(split_order):
        offsets = x + (idx - 0.5) * width
        heights = [values[m][split] for m in methods]
        ax1.bar(
            offsets,
            heights,
            width=width,
            label=split_label[split],
            color=palette[idx],
            edgecolor="white",
            linewidth=0.7,
        )

    ax1.set_ylabel("Accuracy (%)")
    ax1.set_ylim(0, 100)
    ax1.set_xticks(x)
    ax1.set_xticklabels([labels[m] for m in methods])
    ax1.grid(axis="y", alpha=0.2)
    ax1.set_axisbelow(True)
    ax1.legend(frameon=False, ncol=2, loc="upper left")
    ax1.set_title("A  Accuracy by method", loc="left", fontweight="bold")

    y_positions = np.arange(len(delta_labels))
    deltas_pp = []
    lo_err = []
    hi_err = []
    y_text_offset = 0.06
    for key in delta_labels:
        row = delta_rows[key]
        delta = to_float(row["delta_pp"])
        lo = to_float(row["ci_lo_pp"])
        hi = to_float(row["ci_hi_pp"])
        deltas_pp.append(delta)
        lo_err.append(delta - lo)
        hi_err.append(hi - delta)

    ax2.errorbar(
        deltas_pp,
        y_positions,
        xerr=[lo_err, hi_err],
        fmt="o",
        color="#B279A2",
        ecolor="#B279A2",
        elinewidth=1.7,
        capsize=4,
        markersize=5.5,
    )
    ax2.axvline(0, color="0.4", linestyle="--", linewidth=1.0)
    ax2.set_yticks(y_positions)
    ax2.set_yticklabels([delta_labels[k] for k in delta_labels])
    ax2.invert_yaxis()
    ax2.set_xlabel("FIX-2+FIX-4 minus baseline (pp)")
    ax2.set_xlim(-0.5, 8.0)
    ax2.grid(axis="x", alpha=0.2)
    ax2.set_axisbelow(True)
    ax2.set_title("B  Aggregate-720 paired deltas", loc="left", fontweight="bold")

    for y, delta in zip(y_positions, deltas_pp, strict=True):
        ax2.text(delta + 0.12, y + y_text_offset, f"{delta:.2f}", va="center", fontsize=8)

    save_fig(fig, "figure2_accuracy_ci")
    plt.close(fig)


def make_failure_breakdown() -> None:
    rows = read_csv(DATA_DIR / "figure_data_failure_breakdown.csv")
    root_rows = [r for r in rows if r["level"] == "root_cause"]
    subtype_rows = [r for r in rows if r["level"] == "all_methods_wrong_subtype"]

    root_label_map = {
        "all_methods_wrong": "All methods wrong",
        "parser_or_canonicalization_issue": "Parser / canonicalization",
        "present_not_selected": "Present not selected",
    }
    subtype_label_map = {
        "multi_step_composition_trap": "Multi-step composition trap",
        "near_miss_numeric_error": "Near-miss numeric error",
        "different_wrong_answers_no_correct_cluster": "Different wrong answers,\nno correct cluster",
        "same_wrong_answer_false_consensus": "Same wrong answer,\nfalse consensus",
        "shared_unit_or_rate_trap": "Shared unit / rate trap",
        "quantity_selection_trap": "Quantity selection trap",
    }

    fig, (ax1, ax2) = plt.subplots(
        1,
        2,
        figsize=(9.2, 4.8),
        constrained_layout=True,
    )

    root_rows = sorted(root_rows, key=lambda r: int(r["count"]), reverse=True)
    y1 = np.arange(len(root_rows))
    counts1 = [int(r["count"]) for r in root_rows]
    labels1 = [root_label_map[r["label"]] for r in root_rows]
    bars1 = ax1.barh(y1, counts1, color="#72B7B2", edgecolor="white", linewidth=0.7)
    ax1.set_yticks(y1)
    ax1.set_yticklabels(labels1)
    ax1.invert_yaxis()
    ax1.set_xlim(0, 26)
    ax1.set_xlabel("Cases")
    ax1.set_title("A  Root-cause breakdown", loc="left", fontweight="bold")
    ax1.grid(axis="x", alpha=0.2)
    ax1.set_axisbelow(True)
    for bar, count in zip(bars1, counts1, strict=True):
        ax1.text(count + 0.4, bar.get_y() + bar.get_height() / 2, str(count), va="center", fontsize=8)

    subtype_rows = sorted(subtype_rows, key=lambda r: int(r["count"]), reverse=True)
    y2 = np.arange(len(subtype_rows))
    counts2 = [int(r["count"]) for r in subtype_rows]
    labels2 = [fill(subtype_label_map[r["label"]], width=28) for r in subtype_rows]
    bars2 = ax2.barh(y2, counts2, color="#F58518", edgecolor="white", linewidth=0.7)
    ax2.set_yticks(y2)
    ax2.set_yticklabels(labels2)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 11)
    ax2.set_xlabel("Cases within all-methods-wrong")
    ax2.set_title("B  All-methods-wrong subtypes", loc="left", fontweight="bold")
    ax2.grid(axis="x", alpha=0.2)
    ax2.set_axisbelow(True)
    for bar, count in zip(bars2, counts2, strict=True):
        ax2.text(count + 0.25, bar.get_y() + bar.get_height() / 2, str(count), va="center", fontsize=8)

    save_fig(fig, "figure3_failure_breakdown")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    make_accuracy_ci()
    make_failure_breakdown()


if __name__ == "__main__":
    main()
