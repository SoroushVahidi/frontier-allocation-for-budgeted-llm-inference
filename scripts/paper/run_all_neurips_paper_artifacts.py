#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCRIPTS = [
    "build_figure1_problem_setup_data.py",
    "build_main_frontier_plot_data.py",
    "build_allocation_and_failure_plot_data.py",
    "build_paper_tables.py",
    "plot_figure1_problem_setup.py",
    "plot_figure2_main_frontier.py",
    "plot_figure3_oracle_gap.py",
    "plot_figure4_allocation_composition.py",
    "plot_figure5_anti_collapse.py",
    "plot_figure6_failure_decomposition.py",
    "plot_figure7_per_dataset_summary.py",
    "plot_appendix_output_layer_repair.py",
    "plot_appendix_figures.py",
]


def run_script(name: str) -> None:
    cmd = [sys.executable, str(ROOT / name)]
    subprocess.run(cmd, check=True)


def main() -> None:
    built = []
    for script in SCRIPTS:
        run_script(script)
        built.append(script)

    print("=== NeurIPS paper artifacts build completed ===")
    for script in built:
        print(f"- {script}")
    print("Output roots:")
    print("- outputs/paper_plot_data")
    print("- outputs/paper_figures")
    print("- outputs/paper_tables")


if __name__ == "__main__":
    main()
