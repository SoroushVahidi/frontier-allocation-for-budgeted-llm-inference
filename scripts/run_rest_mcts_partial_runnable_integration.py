#!/usr/bin/env python3
"""Deprecated wrapper for ReST-MCTS adjacent integration lane.

Use scripts/run_rest_mcts_adjacent_integration.py directly.
This wrapper is kept for backward compatibility with older docs/commands.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_rest_mcts_adjacent_integration.py"),
        "--contract-config",
        str(REPO_ROOT / "configs" / "rest_mcts_adjacent_comparison_contract_v2.json"),
    ]
    proc = subprocess.run(cmd)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
