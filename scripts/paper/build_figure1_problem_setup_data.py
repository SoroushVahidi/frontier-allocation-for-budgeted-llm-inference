#!/usr/bin/env python3
from __future__ import annotations

from paper_data_sources import PLOT_DATA_DIR, write_json


def main() -> None:
    payload = {
        "figure_id": "figure1_problem_setup",
        "title": "Frontier allocation for budgeted reasoning",
        "nodes": [
            {"id": "input", "label": "Input Question", "kind": "input"},
            {"id": "branches", "label": "Active Branches", "kind": "state"},
            {"id": "scoring", "label": "Branch Scoring", "kind": "decision"},
            {"id": "commit", "label": "Commit / Expand", "kind": "decision"},
            {"id": "support", "label": "Answer-Group Support", "kind": "process"},
            {"id": "anticollapse", "label": "Anti-collapse Control", "kind": "process"},
            {"id": "final", "label": "Final Answer", "kind": "output"},
        ],
        "edges": [
            ["input", "branches"],
            ["branches", "scoring"],
            ["scoring", "commit"],
            ["commit", "final"],
            ["support", "scoring"],
            ["anticollapse", "scoring"],
        ],
        "notes": [
            "Fixed budget limits total test-time compute.",
            "Diagnostics separate absent-from-tree from present-but-misselected failures.",
        ],
    }
    write_json(PLOT_DATA_DIR / "figure1_problem_setup.json", payload)


if __name__ == "__main__":
    main()
