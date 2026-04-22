#!/usr/bin/env python3
from __future__ import annotations

from paper_data_sources import PLOT_DATA_DIR, write_json


def main() -> None:
    payload = {
        "figure_id": "figure1_problem_setup",
        "title": "Frontier allocation under a fixed budget",
        "labels": {
            "input": "Input Question",
            "frontier": "Active Frontier",
            "branch_a": "Branch A",
            "branch_b": "Branch B",
            "branch_c": "Branch C",
            "choose": "Choose Next Action",
            "expand": "Expand one branch",
            "commit": "Commit",
            "final": "Final Answer",
        },
    }
    write_json(PLOT_DATA_DIR / "figure1_problem_setup.json", payload)


if __name__ == "__main__":
    main()
