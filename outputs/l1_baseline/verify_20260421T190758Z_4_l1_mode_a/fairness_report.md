# Fairness report: L1 baseline integration

## Primary comparison policy
- Primary manuscript-safe comparison is `adaptive_min_expand_1` vs `external_l1_exact` and `external_l1_max` under unchanged base-model settings.
- All compared methods share sampled examples, seeds, and action-budget grid.

## L1 variant handling
- `external_l1_exact` maps to LCPO-Exact-style instruction conditioning (exact target length).
- `external_l1_max` maps to LCPO-Max-style instruction conditioning (upper-bound length).

## Budget matching policy
- Internal action budgets are mapped to token-equivalent budgets via 1 action = 64.0 token-equivalent units.
- We report both action-budget and generated-token-estimate fields for auditability.

## Caveats
- Inference-only adapter does not reproduce RL training or official L1 checkpoints.
- MODE B remains blocked unless official/full outputs are imported.
- Control granularity differs from frontier stop-vs-act control; comparisons are matched-budget, not control-identical.
