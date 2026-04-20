#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from build_plot_data import build_all_plot_data
from build_tables import build_all_tables

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_plot(script_name: str, output_path: Path) -> None:
    cmd = [sys.executable, str(Path(__file__).resolve().parent / script_name), "--output", str(output_path)]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NeurIPS paper-facing text artifacts")
    parser.add_argument("--render-plots", action="store_true", help="Also render PNG figures locally")
    parser.add_argument("--plot-output-dir", default="outputs/paper_figures_local", help="Directory for local figure binaries")
    args = parser.parse_args()

    built_plot_data = build_all_plot_data()
    built_tables = build_all_tables()

    rendered = []
    if args.render_plots:
        out_dir = REPO_ROOT / args.plot_output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        plot_jobs = [
            ("plot_main_frontier.py", out_dir / "figure2_main_frontier.png"),
            ("plot_oracle_gap.py", out_dir / "figure3_oracle_gap.png"),
            ("plot_allocation_composition.py", out_dir / "figure4_allocation_composition.png"),
            ("plot_anti_collapse.py", out_dir / "figure5_anti_collapse.png"),
            ("plot_failure_decomposition.py", out_dir / "figure6_failure_decomposition.png"),
            ("plot_per_dataset_frontiers.py", out_dir / "figure7_per_dataset_frontier.png"),
        ]
        for script, output in plot_jobs:
            _run_plot(script, output)
            rendered.append(output)

    print("=== NeurIPS Paper Artifact Build Summary ===")
    print(f"Plot data artifacts: {len(built_plot_data)}")
    for p in built_plot_data:
        print(f"  - {p}")
    print(f"Table artifacts: {len(built_tables)}")
    for p in built_tables:
        print(f"  - {p}")
    print(f"Rendered figure binaries: {len(rendered)}")
    for p in rendered:
        print(f"  - {p}")


if __name__ == "__main__":
    main()
