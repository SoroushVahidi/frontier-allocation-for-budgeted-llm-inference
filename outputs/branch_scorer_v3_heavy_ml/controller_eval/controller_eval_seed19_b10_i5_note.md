# Controller evaluation note

This is a lightweight branch-scorer comparison (v4/v5), not RL training and not a full TreeRL reproduction.

## Subtree value definition (v4 target)
- For each branch snapshot at decision t, look at later snapshots of the same branch within the same episode.
- Snapshot utility is 0.7 * future_score + 0.3 * final_branch_correct.
- v4 target is the mean snapshot utility over those future snapshots (fallback to immediate utility if none).

## v5 path-aware, budget-aware additions
- Edge/action types are defined from logged branch operations only: expand and verify (start token when absent).
- All edge/action costs are kept equal to 1; action type only enters as usefulness features.
- Last-two-node summaries: current/previous score, depth, estimated future value, estimated remaining distance-to-terminal.
- Future-value proxy: 0.72*score + 0.18 - depth penalty, clipped to [0,1].
- Distance proxy (in actions): 4.8 - 2.1*score - 0.45*depth - verify bonus, floored at 0.5.
- v5 target is v4 subtree value scaled by budget adequacy: min(1, remaining_budget / distance_proxy).

## v6 target: logged competitive supervision
- At each decision, visible branches are treated as competing candidates in one group.
- Branch utility comes from future logged outcomes in that same episode (max future score, terminal correctness, solved-any).
- Utility is budget-aware via remaining_budget / realized steps-to-terminal from logs (no handcrafted distance proxy).
- v6 supervision blends pairwise win-rate vs peers and a groupwise softmax preference probability.

## Accuracy by method
- adaptive_score_plus_progress: accuracy=0.5856
- adaptive_relative_rank: accuracy=0.5992
- adaptive_learned_branch_score: accuracy=0.5724
- adaptive_learned_branch_score_v4: accuracy=0.5868
- adaptive_learned_branch_score_v5: accuracy=0.5824
- adaptive_learned_branch_score_v6: accuracy=0.5896

- v4 margin over adaptive_relative_rank: -0.0124
- v4 beats adaptive_relative_rank: no
- v5 margin over adaptive_relative_rank: -0.0168
- v5 beats adaptive_relative_rank: no
- v5 margin over adaptive_learned_branch_score_v4: -0.0044
- v5 beats adaptive_learned_branch_score_v4: no
- v6 margin over adaptive_relative_rank: -0.0096
- v6 beats adaptive_relative_rank: no
- v6 margin over adaptive_learned_branch_score_v5: 0.0072
- v6 beats adaptive_learned_branch_score_v5: yes
