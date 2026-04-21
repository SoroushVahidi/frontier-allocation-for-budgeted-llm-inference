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

    fig, ax = plt.subplots(figsize=(3.45, 5.45))
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
        "input": (0.50, 0.88),
        "branches": (0.14, 0.69),
        "scoring": (0.50, 0.69),
        "commit": (0.86, 0.69),
        "support": (0.34, 0.49),
        "anticollapse": (0.66, 0.49),
        "repair": (0.84, 0.36),
        "final": (0.50, 0.28),
    }
    box_mid = (0.24, 0.102)
    box_aux = (0.29, 0.108)
    box_top = (0.30, 0.102)
    box_bottom = (0.30, 0.102)
    box_repair = (0.22, 0.082)
    box_size = {
        "input": box_top,
        "branches": box_mid,
        "scoring": box_mid,
        "commit": box_mid,
        "support": box_aux,
        "anticollapse": box_aux,
        "repair": box_repair,
        "final": box_bottom,
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
            boxstyle="round,pad=0.015,rounding_size=0.018",
            fc=style["fc"],
            ec=style["ec"],
            lw=1.25,
            transform=ax.transAxes,
        )
        if nid == "repair":
            patch.set_alpha(0.82)
            patch.set_linestyle("--")
            patch.set_linewidth(1.05)
        ax.add_patch(
            FancyBboxPatch(
                (x0, y0),  # shadow-like subtle underlay for consistency
                bw,
                bh,
                boxstyle="round,pad=0.015,rounding_size=0.018",
                fc=style["fc"],
                ec="none",
                lw=0.0,
                alpha=0.0,
                transform=ax.transAxes,
            )
        )
        ax.add_patch(patch)
        wrapped = forced_label.get(nid, n["label"])
        ax.text(
            cx,
            cy,
            wrapped,
            ha="center",
            va="center",
            fontsize=7.85 if nid != "repair" else 7.3,
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
    _arrow((anchors["branches"]["right"][0] + 0.015, anchors["branches"]["right"][1]), (anchors["scoring"]["left"][0] - 0.015, anchors["scoring"]["left"][1]))
    _arrow((anchors["scoring"]["right"][0] + 0.015, anchors["scoring"]["right"][1]), (anchors["commit"]["left"][0] - 0.015, anchors["commit"]["left"][1]))
    # Primary direct path to final answer.
    _arrow((anchors["commit"]["bottom"][0] - 0.012, anchors["commit"]["bottom"][1] - 0.006), (anchors["final"]["top"][0] + 0.065, anchors["final"]["top"][1] + 0.008), rad=-0.06)

    # Auxiliary modules feed into Branch Scoring.
    _arrow((anchors["support"]["top"][0], anchors["support"]["top"][1] + 0.006), (anchors["scoring"]["bottom"][0] - 0.055, anchors["scoring"]["bottom"][1] - 0.004))
    _arrow((anchors["anticollapse"]["top"][0], anchors["anticollapse"]["top"][1] + 0.006), (anchors["scoring"]["bottom"][0] + 0.055, anchors["scoring"]["bottom"][1] - 0.004))

    # Optional residual-slice repair path.
    _arrow(
        (anchors["commit"]["bottom"][0], anchors["commit"]["bottom"][1] - 0.004),
        (anchors["repair"]["top"][0], anchors["repair"]["top"][1] + 0.004),
        rad=-0.03,
    )
    _arrow(
        (anchors["repair"]["left"][0] - 0.004, anchors["repair"]["left"][1] - 0.001),
        (anchors["final"]["right"][0] + 0.004, anchors["final"]["right"][1] + 0.005),
        rad=0.05,
    )
    ax.text(
        0.865,
        0.415,
        "optional\nresidual slice",
        ha="center",
        va="center",
        fontsize=6.3,
        color="#6b5b7f",
        transform=ax.transAxes,
    )

    # Secondary diagnostics panel below main flow.
    notes = spec.get("notes", [])[:2]
    panel_x, panel_y, panel_w, panel_h = 0.11, 0.02, 0.78, 0.145
    ax.add_patch(
        FancyBboxPatch(
            (panel_x, panel_y),
            panel_w,
            panel_h,
            boxstyle="round,pad=0.014,rounding_size=0.018",
            fc="#f7f8fa",
            ec="#ccd2da",
            lw=0.95,
            transform=ax.transAxes,
        )
    )
    ax.text(
        panel_x + 0.02,
        panel_y + panel_h - 0.036,
        "Fixed-budget constraints and diagnostics",
        fontsize=7.8,
        fontweight="semibold",
        color="#232a34",
        transform=ax.transAxes,
    )
    for idx, note in enumerate(notes):
        wrapped_note = textwrap.fill(note, width=54)
        ax.text(
            panel_x + 0.02,
            panel_y + panel_h - 0.065 - idx * 0.049,
            f"- {wrapped_note}",
            fontsize=7.2,
            color="#2a2f38",
            transform=ax.transAxes,
            va="top",
        )

    ax.set_title(spec.get("title", "Figure 1"), fontsize=11.0, fontweight="bold", color="#1a1a1a", pad=10.0)
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
