#!/usr/bin/env python3
"""Controller-level evaluation for heuristic and learned branch scorers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import load_model, simulate_controller


METHODS = [
    "adaptive_raw_score",
    "adaptive_score_plus_progress",
    "adaptive_relative_rank",
    "adaptive_eptree_baseline",
    "adaptive_learned_branch_score",
    "adaptive_learned_branch_score_v3",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controller-level scorer evaluation")
    parser.add_argument("--model-dir", default="outputs/branch_scorer_v3/models")
    parser.add_argument("--output", default="outputs/branch_scorer_v3/controller_eval.json")
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--n-init-branches", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    model_map = {
        "adaptive_learned_branch_score": load_model(Path(args.model_dir) / "adaptive_learned_branch_score.json"),
        "adaptive_learned_branch_score_v3": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v3.json"),
    }

    results: dict[str, dict[str, float]] = {}
    for method in METHODS:
        episode_metrics = []
        for _ in range(args.episodes):
            episode_metrics.append(
                simulate_controller(
                    method=method,
                    rng=rng,
                    budget=args.budget,
                    n_init_branches=args.n_init_branches,
                    max_depth=7,
                    finish_prob_base=0.16,
                    answer_noise=0.12,
                    model_map=model_map,
                )
            )

        n = max(1, len(episode_metrics))
        results[method] = {
            "accuracy": sum(1 for r in episode_metrics if r["is_correct"]) / n,
            "solve_rate": sum(1 for r in episode_metrics if r["solved_any"]) / n,
            "avg_actions": sum(float(r["actions_used"]) for r in episode_metrics) / n,
        }

    best_hand = max(
        ["adaptive_raw_score", "adaptive_score_plus_progress", "adaptive_relative_rank", "adaptive_eptree_baseline"],
        key=lambda m: results[m]["accuracy"],
    )
    margin = results["adaptive_learned_branch_score_v3"]["accuracy"] - results[best_hand]["accuracy"]
    summary = {
        "episodes": args.episodes,
        "budget": args.budget,
        "n_init_branches": args.n_init_branches,
        "results": results,
        "best_hand_designed": best_hand,
        "v3_margin_over_best_hand": margin,
        "v3_clearly_beats_best_hand": margin >= 0.02,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
