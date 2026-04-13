#!/usr/bin/env python3
"""Controller-level evaluation for heuristic and learned branch scorers."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import load_model, simulate_controller


METHODS = [
    "adaptive_score_plus_progress",
    "adaptive_relative_rank",
    "adaptive_learned_branch_score",
    "adaptive_learned_branch_score_v4",
    "adaptive_learned_branch_score_v5",
    "adaptive_learned_branch_score_v6",
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
        "adaptive_learned_branch_score_v4": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v4.json"),
        "adaptive_learned_branch_score_v5": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v5.json"),
        "adaptive_learned_branch_score_v6": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v6.json"),
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

    margin_v4_vs_relative_rank = results["adaptive_learned_branch_score_v4"]["accuracy"] - results["adaptive_relative_rank"]["accuracy"]
    margin_v5_vs_relative_rank = results["adaptive_learned_branch_score_v5"]["accuracy"] - results["adaptive_relative_rank"]["accuracy"]
    margin_v5_vs_v4 = results["adaptive_learned_branch_score_v5"]["accuracy"] - results["adaptive_learned_branch_score_v4"]["accuracy"]
    margin_v6_vs_relative_rank = results["adaptive_learned_branch_score_v6"]["accuracy"] - results["adaptive_relative_rank"]["accuracy"]
    margin_v6_vs_v5 = results["adaptive_learned_branch_score_v6"]["accuracy"] - results["adaptive_learned_branch_score_v5"]["accuracy"]
    summary = {
        "episodes": args.episodes,
        "budget": args.budget,
        "n_init_branches": args.n_init_branches,
        "results": results,
        "v4_margin_over_relative_rank": margin_v4_vs_relative_rank,
        "v4_beats_relative_rank": margin_v4_vs_relative_rank > 0.0,
        "v5_margin_over_relative_rank": margin_v5_vs_relative_rank,
        "v5_beats_relative_rank": margin_v5_vs_relative_rank > 0.0,
        "v5_margin_over_v4": margin_v5_vs_v4,
        "v5_beats_v4": margin_v5_vs_v4 > 0.0,
        "v6_margin_over_relative_rank": margin_v6_vs_relative_rank,
        "v6_beats_relative_rank": margin_v6_vs_relative_rank > 0.0,
        "v6_margin_over_v5": margin_v6_vs_v5,
        "v6_beats_v5": margin_v6_vs_v5 > 0.0,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    csv_path = out_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["method", "accuracy", "solve_rate", "avg_actions"])
        writer.writeheader()
        for method_name in METHODS:
            writer.writerow({"method": method_name, **results[method_name]})

    note_path = out_path.with_name(f"{out_path.stem}_note.md")
    note_lines = [
        "# Controller evaluation note",
        "",
        "This is a lightweight branch-scorer comparison (v4/v5), not RL training and not a full TreeRL reproduction.",
        "",
        "## Subtree value definition (v4 target)",
        "- For each branch snapshot at decision t, look at later snapshots of the same branch within the same episode.",
        "- Snapshot utility is 0.7 * future_score + 0.3 * final_branch_correct.",
        "- v4 target is the mean snapshot utility over those future snapshots (fallback to immediate utility if none).",
        "",
        "## v5 path-aware, budget-aware additions",
        "- Edge/action types are defined from logged branch operations only: expand and verify (start token when absent).",
        "- All edge/action costs are kept equal to 1; action type only enters as usefulness features.",
        "- Last-two-node summaries: current/previous score, depth, estimated future value, estimated remaining distance-to-terminal.",
        "- Future-value proxy: 0.72*score + 0.18 - depth penalty, clipped to [0,1].",
        "- Distance proxy (in actions): 4.8 - 2.1*score - 0.45*depth - verify bonus, floored at 0.5.",
        "- v5 target is v4 subtree value scaled by budget adequacy: min(1, remaining_budget / distance_proxy).",
        "",
        "## v6 target: logged competitive supervision",
        "- At each decision, visible branches are treated as competing candidates in one group.",
        "- Branch utility comes from future logged outcomes in that same episode (max future score, terminal correctness, solved-any).",
        "- Utility is budget-aware via remaining_budget / realized steps-to-terminal from logs (no handcrafted distance proxy).",
        "- v6 supervision blends pairwise win-rate vs peers and a groupwise softmax preference probability.",
        "",
        "## Accuracy by method",
    ]
    for method_name in METHODS:
        note_lines.append(f"- {method_name}: accuracy={results[method_name]['accuracy']:.4f}")
    note_lines.extend(
        [
            "",
            f"- v4 margin over adaptive_relative_rank: {summary['v4_margin_over_relative_rank']:.4f}",
            f"- v4 beats adaptive_relative_rank: {'yes' if summary['v4_beats_relative_rank'] else 'no'}",
            f"- v5 margin over adaptive_relative_rank: {summary['v5_margin_over_relative_rank']:.4f}",
            f"- v5 beats adaptive_relative_rank: {'yes' if summary['v5_beats_relative_rank'] else 'no'}",
            f"- v5 margin over adaptive_learned_branch_score_v4: {summary['v5_margin_over_v4']:.4f}",
            f"- v5 beats adaptive_learned_branch_score_v4: {'yes' if summary['v5_beats_v4'] else 'no'}",
            f"- v6 margin over adaptive_relative_rank: {summary['v6_margin_over_relative_rank']:.4f}",
            f"- v6 beats adaptive_relative_rank: {'yes' if summary['v6_beats_relative_rank'] else 'no'}",
            f"- v6 margin over adaptive_learned_branch_score_v5: {summary['v6_margin_over_v5']:.4f}",
            f"- v6 beats adaptive_learned_branch_score_v5: {'yes' if summary['v6_beats_v5'] else 'no'}",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {note_path}")


if __name__ == "__main__":
    main()
