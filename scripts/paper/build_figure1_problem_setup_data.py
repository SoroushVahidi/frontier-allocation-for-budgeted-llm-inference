#!/usr/bin/env python3
from __future__ import annotations

from paper_data_sources import PLOT_DATA_DIR, write_json


def main() -> None:
    payload = {
        "figure_id": "figure1_problem_setup",
        "title": "Fixed-Budget Frontier Allocation for Reasoning",
        "nodes": [
            {"id": "q", "label": "Input Questions", "kind": "input"},
            {"id": "tree", "label": "Active Branches", "kind": "state"},
            {"id": "controllers", "label": "Controller Families", "kind": "process"},
            {"id": "alloc", "label": "Next-Step Budget Allocation", "kind": "decision"},
            {"id": "groups", "label": "Answer-Group-Aware Commit Control", "kind": "process"},
            {"id": "final", "label": "Final Answer Selection", "kind": "output"},
        ],
        "edges": [
            ["q", "tree"],
            ["tree", "controllers"],
            ["controllers", "alloc"],
            ["alloc", "groups"],
            ["groups", "final"],
        ],
        "notes": [
            "Fixed budget governs total test-time compute.",
            "Anti-collapse behavior is tracked via allocation composition and concentration diagnostics.",
            "Failure decomposition distinguishes tree-generation-like vs output-layer-like losses via auditable proxies.",
        ],
    }
    write_json(PLOT_DATA_DIR / "figure1_problem_setup.json", payload)


if __name__ == "__main__":
    main()
