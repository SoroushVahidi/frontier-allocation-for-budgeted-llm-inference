#!/usr/bin/env python3
"""Lightweight repository health check for local development.

This script is intentionally cheap:
- checks canonical files and directories,
- validates that core Python modules can be imported,
- and reports a small, collaborator-friendly status summary.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "requirements.txt",
    REPO_ROOT / "Makefile",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "CANONICAL_INSTALL_AND_DEV.md",
    REPO_ROOT / "scripts" / "README.md",
    REPO_ROOT / "outputs" / "README.md",
    REPO_ROOT / "experiments" / "frontier_router.py",
    REPO_ROOT / "tests" / "test_frontier_router.py",
]

REQUIRED_IMPORTS = [
    "experiments.frontier_router",
]


def main() -> int:
    print("adaptive-reasoning-budget-allocation")
    print("=====================================")
    print(f"Python version: {sys.version.split()[0]}")
    print()

    missing = [str(path.relative_to(REPO_ROOT)) for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        print("Missing canonical paths:")
        for path in missing:
            print(f"- {path}")
        return 1

    failed_imports: list[str] = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception:
            failed_imports.append(name)

    if failed_imports:
        print("Failed imports:")
        for name in failed_imports:
            print(f"- {name}")
        return 1

    print("Repository health check: OK")
    print("Canonical files present, contributor front door is intact, and core import path works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
