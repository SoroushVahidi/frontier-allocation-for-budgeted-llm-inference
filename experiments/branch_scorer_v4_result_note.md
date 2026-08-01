# Learned branch scorer v4 (lightweight subtree-value prototype)

This note documents a lightweight learned-target prototype inspired by future-success style supervision from tree-search literature, but implemented **without RL training**.

## What “subtree value” means here

Given a branch snapshot at decision step `t` in an episode, we define an approximate subtree value from **logged future snapshots of the same branch**:

- Snapshot utility: `0.7 * future_score + 0.3 * final_branch_correct`
- v4 target: mean snapshot utility across all future snapshots at steps `> t`
- Fallback: if no future snapshot exists, use immediate utility at `t`

This is an approximate downstream-utility target from logged trajectories only. It is not PPO and not a full TreeRL/ReST reproduction.

## Added scorer variant

- `adaptive_learned_branch_score_v4`

## Controller-level comparison set

- `adaptive_relative_rank`
- `adaptive_score_plus_progress`
- `adaptive_learned_branch_score`
- `adaptive_learned_branch_score_v3`
- `adaptive_learned_branch_score_v4`

## Commands

```bash
python scripts/build_v3_ranking_dataset.py --output-dir outputs/branch_scorer_v3 --episodes 1200 --budget 14 --seed 7 --n-init-branches 5
python scripts/train_branch_scorer_v3.py --dataset outputs/branch_scorer_v3/branch_scorer_v3_dataset.jsonl --output-dir outputs/branch_scorer_v3
python scripts/evaluate_branch_scorer_controller.py --model-dir outputs/branch_scorer_v3/models --output outputs/branch_scorer_v3/controller_eval.json --episodes 500 --seed 17 --budget 10 --n-init-branches 5
python scripts/evaluate_branch_scorer_robustness.py --model-dir outputs/branch_scorer_v3/models --output-dir outputs/branch_scorer_v3/robustness_v4 --seeds 3,7,11,19,23 --budgets 8,10,12 --init-branches 3,5,7 --episodes 400 --include-score-plus-progress
```

## Key outcomes

- Single controller setting (`episodes=500, budget=10, init=5`): v4 beats `adaptive_relative_rank` by +0.034 accuracy.
- Multi-setting robustness sweep (45 settings): v4 does **not** robustly beat `adaptive_relative_rank` (`mean margin=-0.0069`, win rate `18/45=0.40`).

## Bottleneck if v4 still fails

The target uses only linearized same-branch future snapshots, so it cannot represent true branch-descendant counterfactuals or cross-branch interaction effects. This weakens signal quality and robustness.
