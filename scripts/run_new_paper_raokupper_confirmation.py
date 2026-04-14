#!/usr/bin/env python3
"""One-command bounded confirmation audit for proxy BT vs Rao-Kupper (new-paper)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded Rao-Kupper confirmation audit")
    p.add_argument("--output-root", default="outputs/new_paper/raokupper_confirmation")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seeds", default="81,82,83,84")
    p.add_argument("--subset-size", type=int, default=18)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=130)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--primary-tie-supervision", choices=["none", "strict_tie", "tie_or_uncertain"], default="none")
    p.add_argument("--include-oracle-reference", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_raokupper_resolution_audit.py"),
        "--output-root",
        args.output_root,
        "--dataset",
        args.dataset,
        "--seeds",
        args.seeds,
        "--subset-size",
        str(args.subset_size),
        "--budget",
        str(args.budget),
        "--ranking-episodes",
        str(args.ranking_episodes),
        "--near-tie-margin",
        str(args.near_tie_margin),
        "--primary-tie-supervision",
        args.primary_tie_supervision,
    ]
    if args.run_id:
        cmd.extend(["--run-id", args.run_id])
    if args.include_oracle_reference:
        cmd.append("--include-oracle-reference")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
