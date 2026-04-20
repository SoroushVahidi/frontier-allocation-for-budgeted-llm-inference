#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import save_fig
from paper_style import STYLE


def main() -> None:
    spec_path = PLOT_DATA_DIR / "figure1_problem_setup.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing figure1 spec: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    ax.axis("off")

    nodes = spec["nodes"]
    x_positions = [0.05, 0.21, 0.38, 0.56, 0.75, 0.92]
    y = 0.58
    for n, x in zip(nodes, x_positions):
        ax.text(
            x,
            y,
            n["label"],
            ha="center",
            va="center",
            fontsize=10,
            bbox={"boxstyle": "round,pad=0.35", "fc": "#f7f7f7", "ec": "#2b2b2b", "lw": 1.0},
            transform=ax.transAxes,
        )
    for i in range(len(nodes) - 1):
        ax.annotate(
            "",
            xy=(x_positions[i + 1] - 0.06, y),
            xytext=(x_positions[i] + 0.06, y),
            arrowprops={"arrowstyle": "->", "lw": 1.4, "color": "#333333"},
            xycoords=ax.transAxes,
            textcoords=ax.transAxes,
        )

    note_y = 0.25
    for idx, note in enumerate(spec.get("notes", [])):
        ax.text(0.02, note_y - idx * 0.1, f"- {note}", fontsize=9.5, transform=ax.transAxes)

    ax.set_title(spec.get("title", "Figure 1"), fontsize=STYLE.title_size)
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
