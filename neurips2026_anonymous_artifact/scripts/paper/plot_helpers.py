from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from paper_style import METHOD_COLORS, STYLE, method_sort_key


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required plot data: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Empty plot data: {path}")
    return rows


def save_fig(fig: Any, pdf_path: Path, png_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(pdf_path, dpi=240, bbox_inches="tight")
    fig.savefig(png_path, dpi=260, bbox_inches="tight")
    plt.close(fig)


def apply_axis_style(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=STYLE.title_size)
    ax.set_xlabel(xlabel, fontsize=STYLE.label_size)
    ax.set_ylabel(ylabel, fontsize=STYLE.label_size)
    ax.tick_params(axis="both", labelsize=STYLE.tick_size)
    ax.grid(True, alpha=STYLE.grid_alpha)


def sorted_methods(rows: list[dict[str, str]]) -> list[str]:
    return sorted({r["method"] for r in rows}, key=method_sort_key)


def method_color(name: str) -> str:
    return METHOD_COLORS.get(name, "#666666")
