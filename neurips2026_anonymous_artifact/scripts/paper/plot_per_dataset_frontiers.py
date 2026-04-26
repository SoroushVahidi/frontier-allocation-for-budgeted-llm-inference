#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from common import PLOT_DATA_DIR
from plot_utils import grouped_methods, maybe_save, read_rows, style_ax


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(PLOT_DATA_DIR / "per_dataset_frontiers.csv"))
    p.add_argument("--output", default="")
    args = p.parse_args()

    rows = read_rows(Path(args.input))
    datasets = sorted({r["dataset"] for r in rows})
    if len(datasets) != 1:
        raise ValueError(f"Expected one dataset in canonical per-dataset frontier; found {datasets}")

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for method in grouped_methods(rows):
        mrows = sorted([r for r in rows if r["method"] == method], key=lambda r: int(r["budget"]))
        ax.plot([int(r["budget"]) for r in mrows], [float(r["accuracy"]) for r in mrows], marker="o", label=method)

    style_ax(ax, f"Per-Dataset Frontier ({datasets[0]})", "Budget", "Accuracy")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    maybe_save(fig, args.output or None)


if __name__ == "__main__":
    main()
