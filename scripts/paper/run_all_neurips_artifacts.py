#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "scripts/paper/build_neurips_tables.py",
    "scripts/paper/build_frontier_plot_data.py",
    "scripts/paper/build_oracle_gap_plot_data.py",
    "scripts/paper/build_allocation_composition_plot_data.py",
    "scripts/paper/build_anti_collapse_plot_data.py",
    "scripts/paper/build_appendix_frontier_plot_data.py",
]


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for script in SCRIPTS:
        cmd = [sys.executable, str(repo_root / script)]
        print("[run]", " ".join(cmd))
        subprocess.run(cmd, cwd=repo_root, check=True)
    print("[ok] all NeurIPS artifact tables and plot-data CSVs generated")


if __name__ == "__main__":
    main()
