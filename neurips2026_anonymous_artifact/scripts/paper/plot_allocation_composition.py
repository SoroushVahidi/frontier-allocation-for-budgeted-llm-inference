#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from common import PLOT_DATA_DIR
from plot_utils import maybe_save, read_rows, style_ax


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(PLOT_DATA_DIR / "allocation_composition.csv"))
    p.add_argument("--output", default="")
    args = p.parse_args()

    rows = read_rows(Path(args.input))
    methods = sorted({r["method"] for r in rows})
    if not methods:
        raise ValueError("No methods found in allocation composition data")
    target = methods[0]
    trows = sorted([r for r in rows if r["method"] == target], key=lambda r: (int(r["budget"]), r["family"]))

    budgets = sorted({int(r["budget"]) for r in trows})
    exp_share = []
    ver_share = []
    for b in budgets:
        by_family = {r["family"]: float(r["component_share"]) for r in trows if int(r["budget"]) == b}
        exp_share.append(by_family.get("expansion", 0.0))
        ver_share.append(by_family.get("verification", 0.0))

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.stackplot(budgets, exp_share, ver_share, labels=["Expansion share", "Verification share"], alpha=0.8)
    style_ax(ax, f"Allocation Composition ({target})", "Budget", "Share of Actions")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    maybe_save(fig, args.output or None)


if __name__ == "__main__":
    main()
