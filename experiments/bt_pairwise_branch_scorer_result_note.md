# BT pairwise scalar branch scorer — audit and result note

## Pipeline audit summary (current repository)

- `experiments/branch_scorer_v3.py` currently supports v1-v6 scalar scorers and simulator targets.
- v5/v6 include current + previous snapshots and limited action recency, but not full ordered path windows.
- Existing v6 supervision blends pairwise/groupwise preferences into per-branch labels, but training is still pointwise on branch rows.
- Controller-time inference is scalar argmax over branches (efficient), but branch value estimation is limited by shallow history encoding.

## Why the old encoding is still weaker

- It primarily captures **current + previous** state and action, which can miss trend shape across multiple recent steps.
- It has no explicit ordered window over multiple nodes/edges with masks for short trajectories.
- It does not directly train a BT objective over same-decision branch pairs, so preference structure is only indirectly represented.

## This upgrade (new-paper track)

- Added `v7_ordered_history` features: remaining budget, ordered last-4 nodes, ordered last-3 edges, explicit masks/START padding, and global branch counters.
- Added pairwise dataset builder for same-episode/same-decision branch comparisons with deterministic tie handling.
- Added BT training path using `log-sigmoid(r(A)-r(B))` equivalent logistic formulation over scalar utility differences.
- Kept inference scalar and efficient: score each branch once with `r(branch)`, then choose argmax.

## Result summary

Pilot runs (simulator-backed):

- GSM8K: `outputs/new_paper/bt_pairwise_branch_scorer/20260414T014936Z/`
  - BT pairwise test accuracy: `0.7936`
  - controller accuracy: `adaptive_bt_pairwise=0.6000` vs `adaptive_min_expand_1=0.2667`
- MATH: `outputs/new_paper/bt_pairwise_branch_scorer/20260414T015633Z/`
  - BT pairwise test accuracy: `0.7923`
  - controller accuracy: `adaptive_bt_pairwise=0.5500` vs `adaptive_min_expand_1=0.2000`

Real-model-backed run was attempted with OpenAI mode but could not be completed in this environment session; simulator results above are the grounded outcomes currently available.
