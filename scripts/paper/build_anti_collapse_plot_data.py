#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper.artifact_utils import PAPER_PLOT_DIR, ensure_output_dirs, load_inputs, read_csv, write_csv


def main() -> None:
    ensure_output_dirs()
    inputs = load_inputs()
    slices = read_csv(inputs.imported_run / "signal_slice_summary.csv")
    write_csv(PAPER_PLOT_DIR / "difficulty_slice_performance.csv", slices)


if __name__ == "__main__":
    main()
