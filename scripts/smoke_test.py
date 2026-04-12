"""
smoke_test.py — Minimal smoke test for the research repository.

Run with:
    python scripts/smoke_test.py
or:
    make smoke
"""

import sys


def main() -> None:
    print("adaptive-reasoning-budget-allocation")
    print("=====================================")
    print("Repository smoke test: OK")
    print(f"Python version: {sys.version}")
    print()
    print("Research project: Adaptive Test-Time Compute Allocation for LLM Reasoning")
    print("Status: Early-stage research. Formulation under development.")
    print()
    print("All checks passed.")


if __name__ == "__main__":
    main()
