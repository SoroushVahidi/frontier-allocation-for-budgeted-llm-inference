# Abstention-aware cost-sensitive partial-order pass (2026-04-17)

## Purpose

Implement one bounded abstention-aware optimization pass on top of the existing `partial_order_incomparable` targets so unresolved behavior can be explicitly utility-optimized rather than only post-hoc observed.

## What changed

- Kept the existing incomparability-capable targets and labels (`partial_order_label` in `{j_wins, unresolved, i_wins}`).
- Added one conservative abstention-aware objective/decision extension in `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`:
  - train-time: unresolved class upweight for partial-order ternary model (`--abstention-unresolved-class-upweight`, used as sample-weight multiplier on class 1),
  - inference-time: explicit expected-cost minimization over actions `{predict_j, predict_unresolved, predict_i}` using model probabilities and a fixed 3x3 cost matrix.
- Added machine-readable cost artifact output:
  - `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_20260417/abstention_cost_config.json`.

## Explicit cost design used (single bounded design)

Cost matrix used in this pass:

- correct directional prediction: `0.0`
- wrong directional prediction: `1.0`
- unresolved on directional truth: `0.35`
- directional on unresolved truth: `0.70`
- correct unresolved: `0.10`

Interpretation:
- wrong confident direction is most costly,
- unresolved is allowed and better than wrong confident direction,
- but unresolved is not free, and predicting unresolved everywhere is penalized.

## Matched run produced

- Base labels:
  - `outputs/branch_label_bruteforce/abstain_cost_base_20260417/`
- Target regimes:
  - `outputs/branch_label_bruteforce_targets/abstain_cost_target_regimes_20260417/`
- Matched comparison run:
  - `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_20260417/`

Compared regimes/formulations include:
- binary baseline (`binary_forced`),
- Davidson tie-aware (`ternary_tie` on `davidson_tie_aware` regime),
- soft probabilistic tie-aware (`soft_ternary_tie` on `soft_prob_tie_aware` regime),
- partial-order incomparability old proxy (`partial_order_incomparable`),
- new abstention-aware cost-sensitive partial-order (`partial_order_cost_sensitive_abstain`).

## Key results (3-seed mean; partial-order incomparability regime)

From `ternary_or_abstain_summary.json`:

- `binary_forced`:
  - forced pairwise acc: `0.631`
  - top-1: `0.571`
  - unresolved rate: `0.000`
- `partial_order_incomparable` (old proxy behavior):
  - forced pairwise acc: `0.685`
  - top-1: `0.619`
  - unresolved rate: `0.000`
- `partial_order_cost_sensitive_abstain` (new):
  - accepted pairwise acc: `0.889`
  - coverage: `0.213`
  - unresolved rate: `0.787`
  - forced pairwise acc (with fallback): `0.582`
  - top-1: `0.518`

## Success/failure reading for this bounded pass

- **Success criterion (realize unresolved behavior at inference): met.**
  - Old partial-order proxy stayed effectively forced (`unresolved_rate=0.000`).
  - New cost-sensitive partial-order realizes a substantial unresolved region (`unresolved_rate=0.787`).
- **Caveat:** unresolved usage is likely too aggressive under this conservative utility (`coverage=0.213`), reducing forced/top-1 metrics.

## What remains unresolved

Main remaining issue is operating point quality (coverage vs deferred honesty) rather than lack of unresolved realization.

Most likely next bounded step:
- keep this cost-sensitive scaffold,
- retune utility (especially unresolved penalties and unresolved class upweight),
- optionally combine with reliability-weighted hard-pair cleanup before retraining.
