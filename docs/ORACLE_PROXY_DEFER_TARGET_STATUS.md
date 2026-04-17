# Oracle-proxy defer target status

## Why heuristic defer labels are limited
The prior defer target used fixed ambiguity thresholds (margin/relative margin/std/outside-gap). This is useful but can over-label defer whenever a pair looks locally uncertain, even when immediate commitment may still be budget-efficient for the next allocation step.

## What oracle_proxy defer targets approximate
`defer_target_mode=oracle_proxy` upgrades defer labels to a bounded oracle-derived proxy based on already-available supervision artifacts. The target asks whether immediate forced left/right commitment appears weak under bounded evidence.

Current proxy components include:
- `pair_value_gap` (small i-vs-j estimated-value gap),
- `pair_gap_over_uncertainty` (gap normalized by uncertainty),
- `pair_best_vs_outside_gap` (pair best vs outside/defer competitiveness),
- `disagreement_risk_score` and `pair_both_below_outside_flag`.

A simple additive rule forms `pair_oracle_defer_score`; defer is triggered when the score is high enough (currently `>=2`). This is explicitly a proxy, not exact global oracle optimality.

## Artifact-backed signals vs bounded proxies
Artifact-backed (directly from labels/candidates):
- `estimated_value_if_allocate_next`,
- `allocation_value_std`,
- `branch_vs_outside_gap`,
- pair label/margin metadata and provenance slices.

Bounded proxies (derived, auditable):
- `pair_gap_over_uncertainty`,
- `pair_commitment_strength_proxy`,
- `pair_oracle_defer_score`,
- `outside_option_should_have_won_proxy` diagnostics.

## Calibration and selective policy layer
For 3-way defer classification, supported calibration modes are:
- `none`,
- `temperature` (global logit temperature fitted on validation),
- `platt` (binary defer-vs-not-defer Platt mapping on validation, with bounded redistribution).

Selective decision policy uses:
- `defer_decision_threshold`,
- `min_commit_confidence`,
- `commit_margin_threshold`.

## Tradeoff metrics to inspect first
1. `accepted_only_accuracy_test` and `coverage_test` together.
2. `defer_f1_test` (and precision/recall traces across threshold).
3. Hard-slice accepted accuracy:
   - `near_tie_accepted_accuracy_test`,
   - `adjacent_rank_accepted_accuracy_test`,
   - `exact_promoted_hard_region_accepted_accuracy_test`.
4. Threshold summaries:
   - best accepted accuracy under minimum coverage,
   - best coverage under minimum accepted accuracy.

## Safe interpretation
- This remains a bounded approximation to budget-aware unresolved-state supervision.
- Positive deltas suggest target quality/label realism matters in addition to representation.
- Mixed or negative deltas still localize bottlenecks (target construction vs calibration/policy thresholding).
