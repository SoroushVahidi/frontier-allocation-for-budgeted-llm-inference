#!/usr/bin/env python3
"""Public-release repository health check."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REQUIRED_PATHS = [
    "README.md",
    "LICENSE",
    "CITATION.cff",
    "pyproject.toml",
    "requirements.txt",
    "Makefile",
    "docs/README.md",
    "docs/REPRODUCIBILITY.md",
    "docs/REPOSITORY_LAYOUT.md",
    "docs/DATASETS.md",
    "docs/ARTIFACT_MAP.md",
    "paper_performance_evaluation/main.tex",
    "paper_performance_evaluation/main.pdf",
    "paper_performance_evaluation/main_with_titlepage.tex",
    "paper_performance_evaluation/main_with_titlepage.pdf",
    "paper_performance_evaluation/supplementary_material/README.md",
    "outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv",
    "experiments/frontier_router.py",
    "experiments/support_aware_selector.py",
    "tests/test_frontier_router.py",
    "tests/test_support_aware_selector.py",
]

REQUIRED_IMPORTS = [
    "experiments.frontier_router",
    "experiments.support_aware_selector",
]


def main() -> int:
    missing = [path for path in REQUIRED_PATHS if not (REPO_ROOT / path).exists()]
    if missing:
        print("Missing public-release paths:")
        for path in missing:
            print(f"- {path}")
        return 1

    for module in REQUIRED_IMPORTS:
        importlib.import_module(module)

    print("Public release health check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

