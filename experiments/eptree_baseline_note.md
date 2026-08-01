# Lightweight `adaptive_eptree_baseline` note

## What this baseline approximates
This baseline is a lightweight approximation of TreeRL/EPTree-style fixed-budget branching:
- maintain multiple active branches,
- allocate each next expansion to the most uncertain branch,
- uncertainty proxy combines score entropy, local instability (`|recent_delta|`, stalled steps), and a shallow-depth bonus.

## What is simplified
- No policy network or RL training.
- No Monte Carlo tree backup/value propagation.
- No claim of full TreeRL/EPTree reproduction.
- This is only a fair, lightweight fixed-budget uncertainty-first comparator within the current simulator framework.

## Controller-level snapshot (seed=19, budget=10, init_branches=5, episodes=1000)
- `adaptive_relative_rank`: 0.589
- `adaptive_learned_branch_score_v3`: 0.587
- `adaptive_learned_branch_score`: 0.593
- `adaptive_eptree_baseline`: 0.562

## Conclusion
- `adaptive_eptree_baseline` does **not** beat `adaptive_relative_rank`.
- `adaptive_eptree_baseline` does **not** beat `adaptive_learned_branch_score_v3`.
- In this setup, the uncertainty-first heuristic is a useful external-style comparator, but not a new top baseline.
