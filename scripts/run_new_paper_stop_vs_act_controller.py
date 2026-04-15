#!/usr/bin/env python3
"""Canonical lightweight wrapper for stop-vs-act dataset build + train/eval."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stop-vs-act lightweight pipeline")
    parser.add_argument("--output-dir", default="outputs/stop_vs_act_controller")
    parser.add_argument("--episodes", type=int, default=1200)
    parser.add_argument("--budget", type=int, default=14)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--eval-episodes", type=int, default=500)
    parser.add_argument("--instability-guard-band", type=float, default=None)
    parser.add_argument(
        "--uncertain-policy",
        choices=["none", "filter", "downweight", "downweight_nonpositive"],
        default="downweight",
    )
    return parser.parse_args()


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "build_stop_vs_act_dataset.py"),
            "--output-dir",
            str(output_dir),
            "--episodes",
            str(args.episodes),
            "--budget",
            str(args.budget),
            "--seed",
            str(args.seed),
            *(
                ["--instability-guard-band", str(args.instability_guard_band)]
                if args.instability_guard_band is not None
                else []
            ),
        ]
    )

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "train_stop_vs_act_controller.py"),
            "--dataset",
            str(output_dir / "stop_vs_act_dataset.jsonl"),
            "--output-dir",
            str(output_dir),
            "--seed",
            str(args.seed),
            "--budget",
            str(args.budget),
            "--eval-episodes",
            str(args.eval_episodes),
            "--uncertain-policy",
            str(args.uncertain_policy),
        ]
    )


if __name__ == "__main__":
    main()
