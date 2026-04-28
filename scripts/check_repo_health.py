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
import traceback

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "QUICKSTART.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "TODO.md",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "requirements.txt",
    REPO_ROOT / "requirements-dev.txt",
    REPO_ROOT / "Makefile",
    REPO_ROOT / "docs" / "CANONICAL_START_HERE.md",
    REPO_ROOT / "docs" / "MANUSCRIPT_SUPPORT_DASHBOARD.md",
    REPO_ROOT / "docs" / "CANONICAL_EXPERIMENT_STACK.md",
    REPO_ROOT / "docs" / "REPO_MAP.md",
    REPO_ROOT / "docs" / "CANONICAL_INSTALL_AND_DEV.md",
    REPO_ROOT / "docs" / "PAPER_SOURCE_OF_TRUTH.md",
    REPO_ROOT / "docs" / "PAPER_CLAIMS_AND_EVIDENCE_MAP.md",
    REPO_ROOT / "docs" / "PAPER_BASELINE_HONESTY_STATUS.md",
    REPO_ROOT / "docs" / "PAPER_OPEN_GAPS_AND_RISKS.md",
    REPO_ROOT / "scripts" / "CANONICAL_START_HERE.md",
    REPO_ROOT / "scripts" / "README.md",
    REPO_ROOT / "scripts" / "paper" / "run_all_neurips_paper_artifacts.py",
    REPO_ROOT / "scripts" / "paper" / "run_all_neurips_artifacts.py",
    REPO_ROOT / "outputs" / "README.md",
    REPO_ROOT / "outputs" / "paper_tables",
    REPO_ROOT / "outputs" / "paper_plot_data",
    REPO_ROOT / "outputs" / "paper_figures",
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

    failed_imports: list[tuple[str, str, str]] = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            failed_imports.append((name, f"{type(exc).__name__}: {exc}", tb))

    if failed_imports:
        print("Failed imports:")
        for name, detail, tb in failed_imports:
            print(f"- {name} ({detail})")
            print("  Traceback (tail):")
            for line in tb.splitlines()[-12:]:
                print(f"  {line}")
        return 1

    print("Repository health check: OK")
    print("Canonical front door, artifact runners, and core import paths are intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
