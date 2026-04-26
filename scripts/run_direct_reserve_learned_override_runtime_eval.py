#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline runtime eval helper for direct-reserve learned override.")
    p.add_argument("--validation-output", required=True, help="Path to an existing cohere direct-reserve validation output directory.")
    p.add_argument("--output-dir", default="", help="Optional explicit output directory for pairing debug artifacts.")
    p.add_argument("--case-limit", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(repo / "scripts" / "debug_direct_reserve_learned_override_pairing.py"),
        "--validation-output",
        str(args.validation_output),
    ]
    if args.output_dir:
        cmd.extend(["--output-dir", str(args.output_dir)])
    if args.case_limit > 0:
        cmd.extend(["--case-limit", str(args.case_limit)])
    subprocess.run(cmd, check=True, cwd=repo)


if __name__ == "__main__":
    main()

