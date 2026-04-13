#!/usr/bin/env python3
"""Build branch-scorer datasets with decision-point labels for v1/v2/v3/v4."""

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
    SimBranch,
    branch_features,
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
                }
                row.update(features)
                rows.append(row)
                episode_row_indices_by_branch[branch.branch_id].append(len(rows) - 1)


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

    dataset_path = out_dir / "branch_scorer_v3_dataset.jsonl"
    with dataset_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    meta = {
        "episodes": args.episodes,
        "budget": args.budget,
        "feature_names": FEATURE_NAMES,
        "n_init_branches": args.n_init_branches,
        "rows": len(rows),
        "train_rows": sum(1 for r in rows if r["split"] == "train"),
        "test_rows": sum(1 for r in rows if r["split"] == "test"),
        "target_definitions": {
            "v3_target_progress_value": "continuation-value proxy from expected immediate gain + confidence - depth penalty",
            "v4_target_subtree_value": "mean downstream utility from future snapshots of the same branch within an episode, utility=0.7*future_score+0.3*final_branch_correct",
        },
    }
    (out_dir / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote dataset to {dataset_path}")


if __name__ == "__main__":
    main()
