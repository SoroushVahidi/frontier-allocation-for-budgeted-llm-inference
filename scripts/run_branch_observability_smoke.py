#!/usr/bin/env python3
"""Bounded smoke run for branch-observability instrumentation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_target_construction import FrontierTargetConstructionConfig, run_frontier_target_construction


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("branch_observability_smoke_%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs/frontier_target_construction" / run_id
    trace_path = out_dir / "smoke_trace_input.jsonl"

    trace_rows = [
        {
            "episode_id": 0,
            "decision_id": 0,
            "remaining_budget": 3,
            "split": "test",
            "dataset_name": "openai/gsm8k",
            "example_id": "openai_gsm8k_smoke_0",
            "answer": "#### 14",
            "active_branches": [
                {
                    "branch_id": "b0",
                    "score": 0.71,
                    "depth": 1,
                    "verify_count": 0,
                    "stalled_steps": 0,
                    "recent_delta": 0.12,
                    "branch_age": 1,
                    "is_done": 0,
                    "is_pruned": 0,
                    "action_history": ["expand"],
                    "score_history": [0.59],
                    "depth_history": [0],
                    "parent_relative_score": 0.04,
                    "branch_reasoning_text_raw": "I compute 8 + 6 = 14 so the total is 14.",
                    "branch_final_answer_text_raw": "14",
                    "branch_text_raw": "I compute 8 + 6 = 14 so the total is 14. Final answer: 14",
                    "generation_metadata": {"generator": "smoke_fixture", "policy": "manual"},
                },
                {
                    "branch_id": "b1",
                    "score": 0.66,
                    "depth": 1,
                    "verify_count": 1,
                    "stalled_steps": 1,
                    "recent_delta": -0.02,
                    "branch_age": 2,
                    "is_done": 0,
                    "is_pruned": 0,
                    "action_history": ["expand", "verify"],
                    "score_history": [0.67, 0.66],
                    "depth_history": [0, 1],
                    "parent_relative_score": -0.01,
                    "branch_reasoning_text_raw": "I tried 8 + 5 = 13, maybe off by 1.",
                    "branch_final_answer_text_raw": "13",
                    "branch_text_raw": "I tried 8 + 5 = 13, maybe off by 1. Final answer: 13",
                    "generation_metadata": {"generator": "smoke_fixture", "policy": "manual"},
                },
            ],
        }
    ]
    _write_jsonl(trace_path, trace_rows)

    cfg = FrontierTargetConstructionConfig(
        episodes=1,
        decision_budget=3,
        n_init_branches=2,
        max_branches_per_state=2,
        rollouts_per_branch=2,
        seed=11,
        train_ratio=0.0,
    )
    result = run_frontier_target_construction(cfg, output_dir=out_dir, trace_jsonl=trace_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
