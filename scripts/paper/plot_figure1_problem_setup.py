#!/usr/bin/env python3
from __future__ import annotations

import json
import textwrap

from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import save_fig


def main() -> None:
    spec_path = PLOT_DATA_DIR / "figure1_problem_setup.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing figure1 spec: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(3.45, 5.7))
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
    # Minimal single-column layout: dominant vertical flow + two side auxiliaries.
    node_pos = {
        "input": (0.50, 0.90),
        "branches": (0.50, 0.77),
        "scoring": (0.50, 0.64),
        "commit": (0.50, 0.51),
        "final": (0.50, 0.38),
        "support": (0.23, 0.64),
        "anticollapse": (0.77, 0.64),
        "repair": (0.78, 0.455),
    }
    main_size = (0.32, 0.092)      # equal width for all main flow boxes
    side_size = (0.24, 0.086)      # smaller side modules
    repair_size = (0.20, 0.072)    # smallest, secondary optional module
    box_size = {
        "input": main_size,
        "branches": main_size,
        "scoring": main_size,
        "commit": main_size,
        "final": main_size,
        "support": side_size,
        "anticollapse": side_size,
        "repair": repair_size,
    }
    forced_label = {
        "input": "Input\nQuestion",
        "branches": "Active\nBranches",
        "scoring": "Branch Scoring /\nAllocation",
        "commit": "Commit\nDecision",
        "support": "Answer-Support\nAggregation",
        "anticollapse": "Anti-collapse +\nRepeat Control",
        "repair": "Bounded Output\nRepair",
        "final": "Final\nAnswer",
    }

    anchors: dict[str, dict[str, tuple[float, float]]] = {}

    for nid, (cx, cy) in node_pos.items():
        if nid not in node_map:
            continue
        n = node_map[nid]
        bw, bh = box_size[nid]
        style = kind_style.get(n.get("kind", ""), default_style)
        x0, y0 = cx - bw / 2, cy - bh / 2
        patch = FancyBboxPatch(
            (x0, y0),
            bw,
            bh,
            boxstyle="round,pad=0.012,rounding_size=0.016",
            fc=style["fc"],
            ec=style["ec"],
            lw=1.25,
            transform=ax.transAxes,
        )
        if nid == "repair":
            patch.set_alpha(0.72)
            patch.set_linestyle("--")
            patch.set_linewidth(1.0)
        ax.add_patch(patch)
        wrapped = forced_label.get(nid, n["label"])
        ax.text(
            cx,
            cy,
            wrapped,
            ha="center",
            va="center",
            fontsize=7.7 if nid != "repair" else 7.0,
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

    # Main vertical flow (short straight arrows).
    _arrow((anchors["input"]["bottom"][0], anchors["input"]["bottom"][1] - 0.006), (anchors["branches"]["top"][0], anchors["branches"]["top"][1] + 0.006))
    _arrow((anchors["branches"]["bottom"][0], anchors["branches"]["bottom"][1] - 0.006), (anchors["scoring"]["top"][0], anchors["scoring"]["top"][1] + 0.006))
    _arrow((anchors["scoring"]["bottom"][0], anchors["scoring"]["bottom"][1] - 0.006), (anchors["commit"]["top"][0], anchors["commit"]["top"][1] + 0.006))
    _arrow((anchors["commit"]["bottom"][0], anchors["commit"]["bottom"][1] - 0.006), (anchors["final"]["top"][0], anchors["final"]["top"][1] + 0.006))

    # Auxiliary modules feed into Branch Scoring.
    _arrow((anchors["support"]["right"][0] + 0.004, anchors["support"]["right"][1]), (anchors["scoring"]["left"][0] - 0.006, anchors["scoring"]["left"][1] - 0.012))
    _arrow((anchors["anticollapse"]["left"][0] - 0.004, anchors["anticollapse"]["left"][1]), (anchors["scoring"]["right"][0] + 0.006, anchors["scoring"]["right"][1] - 0.012))

    # Optional secondary repair path (dashed arrow only as requested).
    ax.annotate(
        "",
        xy=(anchors["repair"]["top"][0], anchors["repair"]["top"][1] + 0.005),
        xytext=(anchors["commit"]["right"][0] + 0.005, anchors["commit"]["right"][1] - 0.005),
        arrowprops={"arrowstyle": "-|>", "lw": 1.1, "color": arrow_color, "linestyle": "--", "mutation_scale": 10},
        xycoords=ax.transAxes,
        textcoords=ax.transAxes,
    )
    _arrow((anchors["repair"]["left"][0] - 0.004, anchors["repair"]["left"][1]), (anchors["final"]["right"][0] + 0.005, anchors["final"]["right"][1]))

    # Secondary diagnostics panel below main flow.
    notes = spec.get("notes", [])[:2]
    panel_x, panel_y, panel_w, panel_h = 0.08, 0.02, 0.84, 0.165
    ax.add_patch(
        FancyBboxPatch(
            (panel_x, panel_y),
            panel_w,
            panel_h,
            boxstyle="round,pad=0.014,rounding_size=0.016",
            fc="#f7f8fa",
            ec="#ccd2da",
            lw=0.95,
            transform=ax.transAxes,
        )
    )
    ax.text(
        panel_x + 0.02,
        panel_y + panel_h - 0.04,
        "Fixed-budget constraints and diagnostics",
        fontsize=7.7,
        fontweight="semibold",
        color="#232a34",
        transform=ax.transAxes,
    )
    for idx, note in enumerate(notes):
        wrapped_note = textwrap.fill(note, width=60)
        ax.text(
            panel_x + 0.02,
            panel_y + panel_h - 0.074 - idx * 0.053,
            f"- {wrapped_note}",
            fontsize=7.05,
            color="#2a2f38",
            transform=ax.transAxes,
            va="top",
        )

    ax.set_title(spec.get("title", "Figure 1"), fontsize=11.0, fontweight="bold", color="#1a1a1a", pad=10.0)
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
