#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import textwrap

from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import save_fig
from paper_style import STYLE


def main() -> None:
    spec_path = PLOT_DATA_DIR / "figure1_problem_setup.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing figure1 spec: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(3.5, 4.6))
    ax.axis("off")

    kind_style = {
        "input": {"fc": "#e8eef8", "ec": "#3a4f6b"},
        "state": {"fc": "#eaf3eb", "ec": "#3d5a40"},
        "process": {"fc": "#f1edf8", "ec": "#4b3f66"},
        "decision": {"fc": "#f8efe4", "ec": "#7b5a2e"},
        "output": {"fc": "#f8e8ea", "ec": "#6d3741"},
    }
    default_style = {"fc": "#f3f4f6", "ec": "#424242"}

    # Wrapped single-column flow: three stages per row with a down-arrow between rows.
    node_pos = {
        "q": (0.18, 0.80),
        "tree": (0.50, 0.80),
        "controllers": (0.82, 0.80),
        "alloc": (0.18, 0.56),
        "groups": (0.50, 0.56),
        "final": (0.82, 0.56),
    }
    box_w, box_h = 0.28, 0.13
    node_anchor: dict[str, tuple[float, float]] = {}

    for n in spec["nodes"]:
        nid = n["id"]
        if nid not in node_pos:
            continue
        cx, cy = node_pos[nid]
        style = kind_style.get(n.get("kind", ""), default_style)
        ax.add_patch(
            FancyBboxPatch(
                (cx - box_w / 2, cy - box_h / 2),
                box_w,
                box_h,
                boxstyle="round,pad=0.01,rounding_size=0.02",
                fc=style["fc"],
                ec=style["ec"],
                lw=1.2,
                transform=ax.transAxes,
            )
        )
        node_anchor[nid] = (cx, cy)
        wrapped = "\n".join(textwrap.wrap(n["label"], width=16))
        ax.text(
            cx,
            cy,
            wrapped,
            ha="center",
            va="center",
            fontsize=8.8,
            color="#1f1f1f",
            transform=ax.transAxes,
        )

    # Explicit wrapped-flow arrows preserve left-to-right stage order.
    arrow_color = "#4a4a4a"

    def _arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={"arrowstyle": "-|>", "lw": 1.2, "color": arrow_color, "mutation_scale": 12},
            xycoords=ax.transAxes,
            textcoords=ax.transAxes,
        )

    _arrow((0.18 + box_w / 2, 0.80), (0.50 - box_w / 2, 0.80))
    _arrow((0.50 + box_w / 2, 0.80), (0.82 - box_w / 2, 0.80))
    _arrow((0.82, 0.80 - box_h / 2), (0.18, 0.56 + box_h / 2))
    _arrow((0.18 + box_w / 2, 0.56), (0.50 - box_w / 2, 0.56))
    _arrow((0.50 + box_w / 2, 0.56), (0.82 - box_w / 2, 0.56))

    # Notes panel with soft background to avoid overlap and preserve readability.
    notes = spec.get("notes", [])
    panel_x, panel_y, panel_w, panel_h = 0.06, 0.08, 0.88, 0.34
    ax.add_patch(
        FancyBboxPatch(
            (panel_x, panel_y),
            panel_w,
            panel_h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            fc="#f6f7f9",
            ec="#c7ccd4",
            lw=1.0,
            transform=ax.transAxes,
        )
    )
    ax.text(
        panel_x + 0.02,
        panel_y + panel_h - 0.06,
        "Fixed-budget constraints and diagnostics",
        fontsize=8.5,
        fontweight="semibold",
        color="#232a34",
        transform=ax.transAxes,
    )
    for idx, note in enumerate(notes):
        wrapped_note = textwrap.fill(note, width=58)
        ax.text(
            panel_x + 0.02,
            panel_y + panel_h - 0.11 - idx * 0.095,
            f"- {wrapped_note}",
            fontsize=8.0,
            color="#2a2f38",
            transform=ax.transAxes,
            va="top",
        )

    ax.set_title(spec.get("title", "Figure 1"), fontsize=STYLE.title_size, color="#1a1a1a")
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
