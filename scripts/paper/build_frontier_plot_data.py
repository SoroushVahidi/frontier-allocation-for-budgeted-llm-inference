#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from scripts.paper.artifact_utils import PAPER_PLOT_DIR, ensure_output_dirs, load_inputs, read_csv, write_csv


def main() -> None:
    ensure_output_dirs()
    inputs = load_inputs()

    imported_frontier = read_csv(inputs.imported_run / "budget_frontier_summary.csv")
    write_csv(PAPER_PLOT_DIR / "main_frontier_curves.csv", imported_frontier)

    summary = json.loads((inputs.imported_run / "summary.json").read_text(encoding="utf-8"))
    fig1_rows = [
        {
            "component": "story_anchor",
            "description": "Fixed-budget cross-controller frontier allocation under heterogeneous families",
            "source_run": str(inputs.imported_run),
        },
        {
            "component": "dataset",
            "description": summary.get("dataset", ""),
            "source_run": str(inputs.imported_run),
        },
        {
            "component": "budget_grid",
            "description": ",".join(str(x) for x in summary.get("budgets", [])),
            "source_run": str(inputs.imported_run),
        },
    ]
    write_csv(PAPER_PLOT_DIR / "figure1_support_metadata.csv", fig1_rows)


if __name__ == "__main__":
    main()
