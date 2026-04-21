#!/usr/bin/env python3
from __future__ import annotations

import json
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

    fig, ax = plt.subplots(figsize=(3.45, 5.35))
    ax.axis("off")

    kind_style = {
        "input": {"fc": "#eaf0f7", "ec": "#3f556f"},
        "state": {"fc": "#e9f2eb", "ec": "#3f6146"},
        "process": {"fc": "#f3eef8", "ec": "#5a4d74"},
        "decision": {"fc": "#f7efe5", "ec": "#7a5a35"},
        "output": {"fc": "#f7e9ec", "ec": "#6f3f4a"},
    }
    default_style = {"fc": "#f3f4f6", "ec": "#4a4a4a"}

    node_map = {n["id"]: n for n in spec["nodes"]}
    # Strict 3-stage vertical flow with separated auxiliary controls.
    node_pos = {
        "input": (0.50, 0.89),
        "branches": (0.15, 0.69),
        "scoring": (0.50, 0.69),
        "commit": (0.85, 0.69),
        "support": (0.33, 0.49),
        "anticollapse": (0.67, 0.49),
        "final": (0.50, 0.30),
    }
    box_wide = (0.23, 0.098)
    box_mid = (0.23, 0.098)
    box_aux = (0.27, 0.10)
    box_top = (0.32, 0.10)
    box_bottom = (0.34, 0.105)
    box_size = {
        "input": box_top,
        "branches": box_mid,
        "scoring": box_mid,
        "commit": box_mid,
        "support": box_aux,
        "anticollapse": box_aux,
        "final": box_bottom,
    }
    anchors: dict[str, dict[str, tuple[float, float]]] = {}

    for nid, (cx, cy) in node_pos.items():
        if nid not in node_map:
            continue
        n = node_map[nid]
        bw, bh = box_size[nid]
        style = kind_style.get(n.get("kind", ""), default_style)
        x0, y0 = cx - bw / 2, cy - bh / 2
        ax.add_patch(
            FancyBboxPatch(
                (x0, y0),
                bw,
                bh,
                boxstyle="round,pad=0.015,rounding_size=0.018",
                fc=style["fc"],
                ec=style["ec"],
                lw=1.25,
                transform=ax.transAxes,
            )
        )
        wrap_width = 18
        if nid in {"branches", "scoring", "commit", "support", "anticollapse"}:
            wrap_width = 12
        wrapped = "\n".join(textwrap.wrap(n["label"], width=wrap_width))
        ax.text(
            cx,
            cy,
            wrapped,
            ha="center",
            va="center",
            fontsize=8.7,
            color="#1e1e1e",
            transform=ax.transAxes,
        )
        anchors[nid] = {
            "left": (x0, cy),
            "right": (x0 + bw, cy),
            "top": (cx, y0 + bh),
            "bottom": (cx, y0),
        }

    arrow_color = "#4b4f56"

    def _arrow(start: tuple[float, float], end: tuple[float, float], *, rad: float = 0.0) -> None:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 1.25,
                "color": arrow_color,
                "mutation_scale": 11,
                "connectionstyle": f"arc3,rad={rad}",
            },
            xycoords=ax.transAxes,
            textcoords=ax.transAxes,
        )

    # Main flow: Input -> Active Branches -> Branch Scoring -> Commit/Expand -> Final Answer.
    _arrow((anchors["input"]["bottom"][0], anchors["input"]["bottom"][1] - 0.008), (anchors["branches"]["top"][0], anchors["branches"]["top"][1] + 0.008))
    _arrow((anchors["branches"]["right"][0] + 0.01, anchors["branches"]["right"][1]), (anchors["scoring"]["left"][0] - 0.01, anchors["scoring"]["left"][1]))
    _arrow((anchors["scoring"]["right"][0] + 0.01, anchors["scoring"]["right"][1]), (anchors["commit"]["left"][0] - 0.01, anchors["commit"]["left"][1]))
    # Route commit->final around the right side to avoid crossing auxiliary text.
    bend_pt = (0.90, 0.42)
    start_pt = (anchors["commit"]["bottom"][0], anchors["commit"]["bottom"][1] - 0.008)
    ax.plot(
        [start_pt[0], bend_pt[0]],
        [start_pt[1], bend_pt[1]],
        color=arrow_color,
        lw=1.25,
        transform=ax.transAxes,
        solid_capstyle="round",
    )
    _arrow((bend_pt[0], bend_pt[1]), (anchors["final"]["top"][0] + 0.10, anchors["final"]["top"][1] + 0.008))

    # Auxiliary modules feed into Branch Scoring.
    _arrow((anchors["support"]["top"][0], anchors["support"]["top"][1] + 0.008), (anchors["scoring"]["bottom"][0] - 0.055, anchors["scoring"]["bottom"][1] - 0.006))
    _arrow((anchors["anticollapse"]["top"][0], anchors["anticollapse"]["top"][1] + 0.008), (anchors["scoring"]["bottom"][0] + 0.055, anchors["scoring"]["bottom"][1] - 0.006))

    # Secondary diagnostics panel below main flow.
    notes = spec.get("notes", [])[:2]
    panel_x, panel_y, panel_w, panel_h = 0.08, 0.04, 0.84, 0.14
    ax.add_patch(
        FancyBboxPatch(
            (panel_x, panel_y),
            panel_w,
            panel_h,
            boxstyle="round,pad=0.014,rounding_size=0.018",
            fc="#f5f6f8",
            ec="#c4cad3",
            lw=1.0,
            transform=ax.transAxes,
        )
    )
    ax.text(
        panel_x + 0.02,
        panel_y + panel_h - 0.042,
        "Fixed-budget constraints and diagnostics",
        fontsize=8.3,
        fontweight="semibold",
        color="#232a34",
        transform=ax.transAxes,
    )
    for idx, note in enumerate(notes):
        wrapped_note = textwrap.fill(note, width=64)
        ax.text(
            panel_x + 0.02,
            panel_y + panel_h - 0.072 - idx * 0.051,
            f"- {wrapped_note}",
            fontsize=7.7,
            color="#2a2f38",
            transform=ax.transAxes,
            va="top",
        )

    ax.set_title(spec.get("title", "Figure 1"), fontsize=10.5, fontweight="bold", color="#1a1a1a", pad=8.0)
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
