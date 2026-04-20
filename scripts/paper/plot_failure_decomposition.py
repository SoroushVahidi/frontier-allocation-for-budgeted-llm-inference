#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from common import PLOT_DATA_DIR
from plot_utils import maybe_save, read_rows, style_ax


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(PLOT_DATA_DIR / "failure_decomposition.csv"))
    p.add_argument("--output", default="")
    args = p.parse_args()

    rows = read_rows(Path(args.input))
    target_method = "Adaptive Budget Guarded"
    mrows = sorted([r for r in rows if r["method"] == target_method], key=lambda r: int(r["budget"]))
    if not mrows:
        mrows = sorted(rows, key=lambda r: (r["method"], int(r["budget"])))
        target_method = mrows[0]["method"]

    budgets = [int(r["budget"]) for r in mrows]
    tree_fail = [float(r["absent_from_tree_failures"]) for r in mrows]
    output_fail = [float(r["present_in_tree_output_layer_failures"]) for r in mrows]

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.stackplot(budgets, tree_fail, output_fail, labels=["Absent-from-tree failures", "Output-layer failures"], alpha=0.85)
    style_ax(ax, f"Failure Decomposition ({target_method})", "Budget", "Failure Rate")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    maybe_save(fig, args.output or None)


if __name__ == "__main__":
    main()
