"""Reproduce all canonical manuscript artifacts (tables, figures, plot data).

This is a reviewer-facing alias for run_all_neurips_paper_artifacts.py.
Running either script produces identical output.

Usage:
    python scripts/paper/reproduce_current_manuscript_artifacts.py

Output roots:
    outputs/paper_tables/
    outputs/paper_figures/
    outputs/paper_plot_data/

No API calls required. No gold labels in prompts. All inputs are local.
"""

from __future__ import annotations

import runpy
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    runpy.run_path(str(_THIS_DIR / "run_all_neurips_paper_artifacts.py"), run_name="__main__")
