#!/usr/bin/env python3
"""Robustness sweep for controller-level branch scorer comparison (including v6)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import load_model, simulate_controller


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-seed robustness sweep for learned branch scorers")
    parser.add_argument("--model-dir", default="outputs/branch_scorer_v3/models")
    parser.add_argument("--output-dir", default="outputs/branch_scorer_v3/robustness")
    parser.add_argument("--seeds", default="3,7,11,19,23")
    parser.add_argument("--budgets", default="8,10,12")
    parser.add_argument("--init-branches", default="3,5,7")
    parser.add_argument("--episodes", type=int, default=400)
    parser.add_argument("--include-score-plus-progress", action="store_true")
    return parser.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(chunk.strip()) for chunk in raw.split(",") if chunk.strip()]


def _method_list(include_progress: bool) -> list[str]:
    methods = [
        "adaptive_relative_rank",
        "adaptive_learned_branch_score",
        "adaptive_learned_branch_score_v4",
        "adaptive_learned_branch_score_v5",
        "adaptive_learned_branch_score_v6",
    ]
    if include_progress:
        methods.insert(1, "adaptive_score_plus_progress")
    return methods


def _evaluate_setting(
    seed: int,
    budget: int,
    n_init_branches: int,
    episodes: int,
    methods: list[str],
    model_map: dict[str, dict[str, Any]],
) -> dict[str, float]:
    rng = random.Random(seed)
    results: dict[str, float] = {}
    for method in methods:
        correct = 0
        for _ in range(episodes):
            episode = simulate_controller(
                method=method,
                rng=rng,
                budget=budget,
                n_init_branches=n_init_branches,
                max_depth=7,
                finish_prob_base=0.16,
                answer_noise=0.12,
                model_map=model_map,
            )
            correct += int(episode["is_correct"])
        results[method] = correct / max(1, episodes)
    return results


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    init_branches = _parse_int_list(args.init_branches)
    methods = _method_list(args.include_score_plus_progress)

    model_map = {
        "adaptive_learned_branch_score": load_model(Path(args.model_dir) / "adaptive_learned_branch_score.json"),
        "adaptive_learned_branch_score_v4": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v4.json"),
        "adaptive_learned_branch_score_v5": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v5.json"),
        "adaptive_learned_branch_score_v6": load_model(Path(args.model_dir) / "adaptive_learned_branch_score_v6.json"),
    }

    rows: list[dict[str, Any]] = []
    v6_margins_vs_relative_rank: list[float] = []
    v6_margins_vs_v5: list[float] = []
    v6_wins_vs_relative_rank = 0

    for seed in seeds:
        for budget in budgets:
            for n_init in init_branches:
                result = _evaluate_setting(seed, budget, n_init, args.episodes, methods, model_map)
                strongest_hand = max([m for m in methods if m != "adaptive_learned_branch_score_v6"], key=lambda m: result[m])
                margin = result["adaptive_learned_branch_score_v6"] - result[strongest_hand]
                margin_vs_relative_rank = result["adaptive_learned_branch_score_v6"] - result["adaptive_relative_rank"]
                margin_vs_v5 = result["adaptive_learned_branch_score_v6"] - result["adaptive_learned_branch_score_v5"]
                v6_margins_vs_relative_rank.append(margin_vs_relative_rank)
                v6_margins_vs_v5.append(margin_vs_v5)
                if margin_vs_relative_rank > 0:
                    v6_wins_vs_relative_rank += 1

                for method_name in methods:
                    rows.append(
                        {
                            "seed": seed,
                            "budget": budget,
                            "init_branches": n_init,
                            "method": method_name,
                            "accuracy": result[method_name],
                            "strongest_hand": strongest_hand,
                            "v6_margin_vs_strongest_hand": margin,
                            "v6_margin_vs_relative_rank": margin_vs_relative_rank,
                            "v6_margin_vs_v5": margin_vs_v5,
                        }
                    )

    by_method: dict[str, list[float]] = {method: [] for method in methods}
    for row in rows:
        by_method[row["method"]].append(float(row["accuracy"]))

    trial_count = len(seeds) * len(budgets) * len(init_branches)
    trial_rows = [r for r in rows if r["method"] == "adaptive_learned_branch_score_v6"]
    best_trial = max(trial_rows, key=lambda r: float(r["v6_margin_vs_relative_rank"]))
    worst_trial = min(trial_rows, key=lambda r: float(r["v6_margin_vs_relative_rank"]))

    summary = {
        "seeds": seeds,
        "budgets": budgets,
        "init_branches": init_branches,
        "episodes_per_setting": args.episodes,
        "methods": methods,
        "method_accuracy_stats": {
            method: {
                "mean_accuracy": statistics.mean(values),
                "std_accuracy": statistics.pstdev(values),
            }
            for method, values in by_method.items()
        },
        "v6_margin_vs_relative_rank_mean": statistics.mean(v6_margins_vs_relative_rank),
        "v6_margin_vs_relative_rank_std": statistics.pstdev(v6_margins_vs_relative_rank),
        "v6_win_rate_vs_relative_rank": v6_wins_vs_relative_rank / max(1, trial_count),
        "v6_win_count_vs_relative_rank": v6_wins_vs_relative_rank,
        "v6_margin_vs_v5_mean": statistics.mean(v6_margins_vs_v5),
        "v6_margin_vs_v5_std": statistics.pstdev(v6_margins_vs_v5),
        "trial_count": trial_count,
        "best_setting_for_v6_margin_vs_relative_rank": {
            "seed": best_trial["seed"],
            "budget": best_trial["budget"],
            "init_branches": best_trial["init_branches"],
            "margin": best_trial["v6_margin_vs_relative_rank"],
        },
        "worst_setting_for_v6_margin_vs_relative_rank": {
            "seed": worst_trial["seed"],
            "budget": worst_trial["budget"],
            "init_branches": worst_trial["init_branches"],
            "margin": worst_trial["v6_margin_vs_relative_rank"],
        },
        "v6_robustly_beats_relative_rank": (
            statistics.mean(v6_margins_vs_relative_rank) > 0
            and (v6_wins_vs_relative_rank / max(1, trial_count)) >= 0.7
        ),
    }

    json_path = output_dir / "robustness_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    csv_path = output_dir / "robustness_per_setting.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "seed",
                "budget",
                "init_branches",
                "method",
                "accuracy",
                "strongest_hand",
                "v6_margin_vs_strongest_hand",
                "v6_margin_vs_relative_rank",
                "v6_margin_vs_v5",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    note_path = output_dir / "robustness_note.md"
    note_lines = [
        "# Branch scorer v6 robustness note",
        "",
        f"- Mean v6 margin vs adaptive_relative_rank: {summary['v6_margin_vs_relative_rank_mean']:.4f}",
        f"- Std v6 margin vs adaptive_relative_rank: {summary['v6_margin_vs_relative_rank_std']:.4f}",
        f"- v6 win rate vs adaptive_relative_rank: {summary['v6_win_rate_vs_relative_rank']:.3f} ({summary['v6_win_count_vs_relative_rank']}/{summary['trial_count']})",
        f"- Mean v6 margin vs adaptive_learned_branch_score_v5: {summary['v6_margin_vs_v5_mean']:.4f}",
        f"- Robustly better vs adaptive_relative_rank? {'yes' if summary['v6_robustly_beats_relative_rank'] else 'no'}",
        "",
        "## Best / worst settings for v6 margin vs adaptive_relative_rank",
        f"- Best: seed={best_trial['seed']}, budget={best_trial['budget']}, init_branches={best_trial['init_branches']}, margin={best_trial['v6_margin_vs_relative_rank']:.4f}",
        f"- Worst: seed={worst_trial['seed']}, budget={worst_trial['budget']}, init_branches={worst_trial['init_branches']}, margin={worst_trial['v6_margin_vs_relative_rank']:.4f}",
    ]
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {note_path}")


if __name__ == "__main__":
    main()
