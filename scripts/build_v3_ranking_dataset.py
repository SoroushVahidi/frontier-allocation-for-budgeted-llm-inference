#!/usr/bin/env python3
"""Build branch-scorer datasets with decision-point labels for v1-v6."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import (
    FEATURE_NAMES,
    V5_FEATURE_NAMES,
    V6_FEATURE_NAMES,
    V7_FEATURE_NAMES,
    SimBranch,
    branch_features,
    branch_features_v5,
    branch_features_v6,
    branch_features_v7_ordered_history,
    continuation_value,
    expected_next_gain,
    expand_branch,
    maybe_verify,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build v1/v2/v3 branch-scorer datasets")
    parser.add_argument("--output-dir", default="outputs/branch_scorer_v3")
    parser.add_argument("--episodes", type=int, default=1200)
    parser.add_argument("--budget", type=int, default=14)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--n-init-branches", type=int, default=5)
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--finish-prob-base", type=float, default=0.16)
    parser.add_argument("--answer-noise", type=float, default=0.12)
    return parser.parse_args()


def _new_branch(rng: random.Random, idx: int) -> SimBranch:
    return SimBranch(
        branch_id=f"branch_{idx}",
        latent_quality=rng.uniform(0.2, 0.95),
        score=rng.uniform(0.25, 0.75),
    )


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for ep in range(args.episodes):
        branches = [_new_branch(rng, i) for i in range(args.n_init_branches)]
        episode_row_indices_by_branch: dict[str, list[int]] = {branch.branch_id: [] for branch in branches}
        episode_row_indices_by_decision: dict[int, list[int]] = {}
        for decision_id in range(args.budget):
            for branch in branches:
                branch.branch_age += 1
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) <= 1:
                if not active:
                    break
                chosen = active[0]
                expand_branch(chosen, rng, args.finish_prob_base, args.answer_noise, args.max_depth)
                continue

            gains = {b.branch_id: expected_next_gain(b, args.finish_prob_base, args.answer_noise) for b in active}
            values = {b.branch_id: continuation_value(b, args.finish_prob_base, args.answer_noise) for b in active}
            best_branch_id = max(active, key=lambda b: gains[b.branch_id]).branch_id
            mean_value = sum(values.values()) / max(1, len(values))
            mean_score = sum(b.score for b in active) / max(1, len(active))

            for branch in active:
                features = branch_features(branch, parent_mean_score=mean_score)
                row = {
                    "episode_id": ep,
                    "decision_id": decision_id,
                    "branch_id": branch.branch_id,
                    "split": "train" if ep < int(args.episodes * args.train_ratio) else "test",
                    "v3_label_top1": int(branch.branch_id == best_branch_id),
                    "v2_label_gain": int(gains[branch.branch_id] >= 0.6 * max(gains.values())),
                    "v1_label_quality": int(branch.score >= 0.62),
                    "v3_target_progress_value": values[branch.branch_id],
                    "v3_target_parent_relative_improvement": values[branch.branch_id] - mean_value,
                    "v4_target_subtree_value": 0.0,
                    "v5_target_budgeted_subtree_value": 0.0,
                    "v6_target_pairwise_groupwise": 0.0,
                    "v6_label_prefers_over_median": 0,
                }
                row.update(features)
                row.update(
                    branch_features_v5(
                        branch=branch,
                        parent_mean_score=mean_score,
                        remaining_budget=max(0, args.budget - decision_id),
                    )
                )
                row.update(
                    branch_features_v6(
                        branch=branch,
                        parent_mean_score=mean_score,
                        remaining_budget=max(0, args.budget - decision_id),
                    )
                )
                row.update(
                    branch_features_v7_ordered_history(
                        branch=branch,
                        parent_mean_score=mean_score,
                        remaining_budget=max(0, args.budget - decision_id),
                    )
                )
                rows.append(row)
                row_idx = len(rows) - 1
                episode_row_indices_by_branch[branch.branch_id].append(row_idx)
                episode_row_indices_by_decision.setdefault(decision_id, []).append(row_idx)


            chosen = rng.choice(active)
            expand_branch(chosen, rng, args.finish_prob_base, args.answer_noise, args.max_depth)
            if not chosen.is_done and rng.random() < 0.35:
                maybe_verify(chosen, rng)

        # Lightweight subtree-value target (v4): approximate downstream branch utility
        # from logged branch trajectory snapshots within the same episode.
        # For each decision-point row, subtree value = mean utility over future snapshots
        # of the same branch at later decisions.
        # utility(snapshot) = 0.7 * score(snapshot) + 0.3 * is_correct_final(branch)
        # If no future snapshot exists, fallback to immediate utility at current row.
        branch_terminal_correct = {branch.branch_id: 1.0 if branch.is_correct else 0.0 for branch in branches}

        for branch_id, indices in episode_row_indices_by_branch.items():
            terminal_correct = branch_terminal_correct.get(branch_id, 0.0)
            for i, row_idx in enumerate(indices):
                future_indices = indices[i + 1 :]
                if future_indices:
                    future_utilities = [
                        0.7 * float(rows[future_idx]["score"]) + 0.3 * terminal_correct
                        for future_idx in future_indices
                    ]
                    rows[row_idx]["v4_target_subtree_value"] = sum(future_utilities) / len(future_utilities)
                else:
                    rows[row_idx]["v4_target_subtree_value"] = 0.7 * float(rows[row_idx]["score"]) + 0.3 * terminal_correct
                distance = float(rows[row_idx]["curr_distance_to_terminal_est"])
                budget = float(rows[row_idx]["remaining_budget"])
                budget_factor = min(1.0, budget / max(1.0, distance))
                rows[row_idx]["v5_target_budgeted_subtree_value"] = rows[row_idx]["v4_target_subtree_value"] * budget_factor

        # Logged-trajectory competitive target (v6):
        # At each decision, compare each visible branch to its competing branches.
        # Utility is derived from future logged outcomes for the same branch, then
        # converted into pairwise and groupwise preference targets.
        solved_any_episode = 1.0 if any(branch.is_correct for branch in branches if branch.is_done) else 0.0
        for decision_id, group_indices in episode_row_indices_by_decision.items():
            if len(group_indices) <= 1:
                rows[group_indices[0]]["v6_target_pairwise_groupwise"] = 0.5
                rows[group_indices[0]]["v6_label_prefers_over_median"] = 1
                continue

            realized_returns: dict[int, float] = {}
            for row_idx in group_indices:
                branch_id = str(rows[row_idx]["branch_id"])
                branch_indices = episode_row_indices_by_branch.get(branch_id, [])
                terminal_correct = branch_terminal_correct.get(branch_id, 0.0)
                branch_position = branch_indices.index(row_idx)
                future_indices = branch_indices[branch_position + 1 :]
                max_future_score = max(
                    [float(rows[k]["score"]) for k in future_indices] + [float(rows[row_idx]["score"])]
                )
                if future_indices:
                    steps_to_terminal = max(1, int(rows[future_indices[-1]]["decision_id"]) - decision_id + 1)
                else:
                    steps_to_terminal = max(1, args.budget - decision_id)
                budget_now = float(rows[row_idx]["remaining_budget"])
                budget_factor = min(1.0, budget_now / float(steps_to_terminal))
                utility = (0.55 * max_future_score + 0.30 * terminal_correct + 0.15 * solved_any_episode) * budget_factor
                realized_returns[row_idx] = utility

            group_values = list(realized_returns.values())
            max_val = max(group_values)
            exps = {idx: pow(2.718281828, realized_returns[idx] - max_val) for idx in group_indices}
            softmax_denom = sum(exps.values())

            median_return = sorted(group_values)[len(group_values) // 2]
            for row_idx in group_indices:
                row_return = realized_returns[row_idx]
                pairwise_wins = 0.0
                for other_idx in group_indices:
                    if other_idx == row_idx:
                        continue
                    pairwise_wins += 1.0 if row_return > realized_returns[other_idx] else 0.0
                    pairwise_wins += 0.5 if row_return == realized_returns[other_idx] else 0.0
                pairwise_rate = pairwise_wins / max(1.0, float(len(group_indices) - 1))
                groupwise_prob = exps[row_idx] / max(1e-9, softmax_denom)
                rows[row_idx]["v6_target_pairwise_groupwise"] = 0.65 * pairwise_rate + 0.35 * groupwise_prob
                rows[row_idx]["v6_label_prefers_over_median"] = int(row_return >= median_return)

    dataset_path = out_dir / "branch_scorer_v3_dataset.jsonl"
    with dataset_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    meta = {
        "episodes": args.episodes,
        "budget": args.budget,
        "feature_names": FEATURE_NAMES,
        "v5_feature_names": V5_FEATURE_NAMES,
        "v6_feature_names": V6_FEATURE_NAMES,
        "v7_feature_names": V7_FEATURE_NAMES,
        "n_init_branches": args.n_init_branches,
        "rows": len(rows),
        "train_rows": sum(1 for r in rows if r["split"] == "train"),
        "test_rows": sum(1 for r in rows if r["split"] == "test"),
        "target_definitions": {
            "v3_target_progress_value": "continuation-value proxy from expected immediate gain + confidence - depth penalty",
            "v4_target_subtree_value": "mean downstream utility from future snapshots of the same branch within an episode, utility=0.7*future_score+0.3*final_branch_correct",
            "v5_target_budgeted_subtree_value": "v4 subtree value scaled by min(1, remaining_budget / curr_distance_to_terminal_est)",
            "v6_target_pairwise_groupwise": "decision-time competitive target from logged future outcomes: budget-aware utility blended into pairwise win-rate and groupwise softmax preference",
            "v7_ordered_history_features": "remaining budget + ordered last-4 nodes and last-3 edges with explicit padding/masks for short branch histories",
        },
    }
    (out_dir / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote dataset to {dataset_path}")


if __name__ == "__main__":
    main()
