# Branch scorer v3 result note (progress-style node value)

## Why v3 is more progress-like than v1/v2
- v1/v2 are still binary-style classifiers (`v1_label_quality`, `v2_label_gain`).
- v3 uses a **non-binary continuation value** target: `v3_target_progress_value`.
- v3 also includes a **parent-relative signal**: `parent_relative_score` feature and `v3_target_parent_relative_improvement` target field.

## Exact v3 target and features
- Main target used for training `adaptive_learned_branch_score_v3`:
  - `v3_target_progress_value = continuation_value(branch)`
  - where continuation value combines expected next gain, current confidence, and depth regularization.
- Additional relative quantity computed in the dataset:
  - `v3_target_parent_relative_improvement = v3_target_progress_value - mean_group_value`.
- Features:
  - `score`, `depth`, `stalled_steps`, `recent_delta`, `verify_count`, `branch_age`, `score_x_depth`, `parent_relative_score`.

## Controller-level comparison
Methods compared:
- `adaptive_raw_score`
- `adaptive_score_plus_progress`
- `adaptive_relative_rank`
- `adaptive_learned_branch_score`
- `adaptive_learned_branch_score_v3`

## Latest result snapshot
- `adaptive_raw_score`: 0.577
- `adaptive_score_plus_progress`: 0.587
- `adaptive_relative_rank`: 0.589 (strongest heuristic)
- `adaptive_learned_branch_score`: 0.585
- `adaptive_learned_branch_score_v3`: 0.600

## Conclusion
- v3 **does beat** `adaptive_relative_rank` in this run (margin: **+0.011**), but not by a large/clear margin.
- Upgrade value: target is now continuation/progress-like and non-binary.

## Current limitation
- Local scalar value supervision still has train-controller mismatch; next bottleneck is better long-horizon credit assignment at decision points.
