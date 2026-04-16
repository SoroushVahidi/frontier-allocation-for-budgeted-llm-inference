# Canonical uncertainty fields for pairwise + outside-option outputs

This note defines the canonical uncertainty fields emitted by:
- pairwise oracle-preference rows (`pairwise_oracle_preferences.jsonl`), and
- outside-option stop-vs-act rows (`stop_vs_act_dataset.jsonl`).

The goal is to keep uncertainty semantics stable across generators and downstream analyses.

## Canonical fields

Each row should include:
- `is_near_tie`
- `tie_margin`
- `abs_margin`
- `utility_std`
- `ci_low`
- `ci_high`
- `n_rollouts`
- `is_uncertain`

### Field semantics

- `abs_margin`:
  - Absolute value of the primary decision margin for that row.
  - Pairwise rows: `abs(approx_oracle_a - approx_oracle_b)`.
  - Outside-option rows: `abs(delta_mean)`, where `delta_mean` is ACT-vs-STOP utility gap.

- `tie_margin`:
  - Threshold used for near-tie classification.
  - Pairwise rows: oracle tie margin config.
  - Outside-option rows: `near_tie_margin` if explicitly configured, else `gain_margin`.

- `is_near_tie`:
  - `1` iff `abs_margin <= tie_margin`, else `0`.

- `utility_std`:
  - Standard-deviation proxy for the row-level utility estimate.
  - Outside-option rows use estimator std (`delta_estimator_std`).
  - Pairwise rows combine per-branch uncertainty conservatively with root-sum-of-squares.

- `n_rollouts`:
  - Effective rollout count used to estimate uncertainty for the row.
  - Outside-option stabilized mode should account for repeats.

- `ci_low`, `ci_high`:
  - 95% normal-approximation confidence interval around the central margin estimate.
  - If no rollouts are available (`n_rollouts <= 0`), interval collapses to point estimate.

- `is_uncertain`:
  - `1` when **any enabled uncertainty rule** fires (OR semantics), else `0`.

## Configurable uncertainty rules

The canonical rules are:
1. **Margin-band rule**: uncertain when `abs_margin <= uncertainty_margin_band`.
2. **CI-overlap rule**: uncertain when CI overlaps zero (`ci_low <= 0 <= ci_high`).
3. **Disagreement-rate rule**: uncertain when disagreement metric exceeds configured threshold.

Implementations may keep additional legacy rules (e.g., instability gates), but should still expose canonical fields above.

## Safe interpretation guidance

- `is_near_tie=1` means **decision margin is small under current estimator**, not that both options are globally equivalent.
- CI fields are local normal approximations, not strict finite-sample guarantees.
- `is_uncertain=1` is a caution flag for filtering, downweighting, or manual audit, not proof that the label is wrong.
- `is_uncertain=0` should still be treated as “no warning triggered,” not “ground truth certainty.”
- Cross-run comparisons should only compare uncertainty rates when threshold configs are matched.

