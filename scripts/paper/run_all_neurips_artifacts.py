#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import subprocess
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    canonical_runner = repo_root / "scripts" / "paper" / "run_all_neurips_paper_artifacts.py"
    cmd = [sys.executable, str(canonical_runner)]
    print("[deprecated] run_all_neurips_artifacts.py is retained for compatibility only.")
    print("[canonical]", " ".join(cmd))
    subprocess.run(cmd, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
