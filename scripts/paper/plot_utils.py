from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from common import METHOD_ORDER


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing plot input: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Empty plot input: {path}")
    return rows


def grouped_methods(rows: list[dict[str, str]]) -> list[str]:
    methods = sorted({r["method"] for r in rows})
    return sorted(methods, key=lambda m: (METHOD_ORDER.index(m) if m in METHOD_ORDER else 999, m))


def style_ax(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.25)


def maybe_save(fig, output: str | None) -> None:
    fig.tight_layout()
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=220)
    else:
        plt.show()
