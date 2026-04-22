#!/usr/bin/env python3
from __future__ import annotations

import json

from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt

from paper_data_sources import FIGURE_DIR, PLOT_DATA_DIR
from plot_helpers import save_fig


def main() -> None:
    spec_path = PLOT_DATA_DIR / "figure1_problem_setup.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing figure1 spec: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(3.45, 4.6))
    ax.axis("off")

    labels = spec.get("labels", {})

    style = {
        "input": {"fc": "#eaf0f7", "ec": "#3f556f"},
        "frontier": {"fc": "#e9f2eb", "ec": "#3f6146"},
        "decision": {"fc": "#f7efe5", "ec": "#7a5a35"},
        "action": {"fc": "#f3eef8", "ec": "#5a4d74"},
        "output": {"fc": "#f7e9ec", "ec": "#6f3f4a"},
        "branch": {"fc": "#ffffff", "ec": "#7c8a9a"},
    }

    def draw_box(cx: float, cy: float, w: float, h: float, text: str, kind: str, fs: float = 8.0) -> dict[str, tuple[float, float]]:
        x0, y0 = cx - w / 2, cy - h / 2
        ax.add_patch(
            FancyBboxPatch(
                (x0, y0),
                w,
                h,
                boxstyle="round,pad=0.012,rounding_size=0.016",
                fc=style[kind]["fc"],
                ec=style[kind]["ec"],
                lw=1.2,
                transform=ax.transAxes,
            )
        )
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color="#1f2430", transform=ax.transAxes)
        return {
            "top": (cx, y0 + h),
            "bottom": (cx, y0),
            "left": (x0, cy),
            "right": (x0 + w, cy),
        }

    anchors = {}
    anchors["input"] = draw_box(0.50, 0.88, 0.30, 0.095, labels.get("input", "Input Question").replace(" ", "\n", 1), "input", 8.0)
    anchors["frontier"] = draw_box(0.50, 0.71, 0.34, 0.14, "", "frontier", 8.2)

    # Three active branches inside frontier box.
    # Keep branch labels minimal for single-column readability.
    ax.text(0.50, 0.728, labels.get("frontier", "Active Frontier"), ha="center", va="center", fontsize=8.2, color="#1f2430", transform=ax.transAxes)
    branch_y = 0.675
    anchors["branch_a"] = draw_box(0.41, branch_y, 0.085, 0.048, "A", "branch", 7.2)
    anchors["branch_b"] = draw_box(0.50, branch_y, 0.085, 0.048, "B", "branch", 7.2)
    anchors["branch_c"] = draw_box(0.59, branch_y, 0.085, 0.048, "C", "branch", 7.2)

    anchors["choose"] = draw_box(0.50, 0.54, 0.34, 0.10, labels.get("choose", "Choose Next Action"), "decision", 8.2)
    anchors["expand"] = draw_box(0.34, 0.39, 0.25, 0.085, labels.get("expand", "Expand one branch"), "action", 7.8)
    anchors["commit"] = draw_box(0.66, 0.39, 0.18, 0.085, labels.get("commit", "Commit"), "action", 8.0)
    anchors["final"] = draw_box(0.50, 0.24, 0.30, 0.095, labels.get("final", "Final Answer"), "output", 8.0)

    arrow_color = "#4b4f56"

    def _arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={"arrowstyle": "-|>", "lw": 1.15, "color": arrow_color, "mutation_scale": 10},
            xycoords=ax.transAxes,
            textcoords=ax.transAxes,
        )

    _arrow((anchors["input"]["bottom"][0], anchors["input"]["bottom"][1] - 0.005), (anchors["frontier"]["top"][0], anchors["frontier"]["top"][1] + 0.005))
    _arrow((anchors["frontier"]["bottom"][0], anchors["frontier"]["bottom"][1] - 0.005), (anchors["choose"]["top"][0], anchors["choose"]["top"][1] + 0.005))
    _arrow((anchors["choose"]["bottom"][0] - 0.065, anchors["choose"]["bottom"][1] - 0.004), (anchors["expand"]["top"][0], anchors["expand"]["top"][1] + 0.004))
    _arrow((anchors["choose"]["bottom"][0] + 0.065, anchors["choose"]["bottom"][1] - 0.004), (anchors["commit"]["top"][0], anchors["commit"]["top"][1] + 0.004))
    _arrow((anchors["expand"]["bottom"][0] + 0.035, anchors["expand"]["bottom"][1] - 0.004), (anchors["final"]["top"][0] - 0.06, anchors["final"]["top"][1] + 0.004))
    _arrow((anchors["commit"]["bottom"][0] - 0.02, anchors["commit"]["bottom"][1] - 0.004), (anchors["final"]["top"][0] + 0.06, anchors["final"]["top"][1] + 0.004))

    ax.set_title(spec.get("title", "Figure 1"), fontsize=11.0, fontweight="bold", color="#1a1a1a", pad=8.0)
    save_fig(fig, FIGURE_DIR / "figure1_problem_setup.pdf", FIGURE_DIR / "figure1_problem_setup.png")


if __name__ == "__main__":
    main()
