# Canonical uncertainty fields schema (pairwise + outside-option labels)

This document defines the canonical uncertainty fields used by:
- pairwise oracle-preference rows (branch-vs-branch), and
- outside-option stop-vs-act rows (branch-vs-outside).

These fields are uncertainty diagnostics for supervision-target quality and **do not** reframe the project away from next-step branch allocation.

## Canonical fields (required)

All pairwise and outside-option rows must include:
- `is_near_tie` (int: 0/1)
- `tie_margin` (float)
- `abs_margin` (float)
- `utility_std` (float)
- `ci_low` (float)
- `ci_high` (float)
- `n_rollouts` (int)
- `is_uncertain` (int: 0/1)

Additionally, outside-option rows include:
- `outside_option_type` (string)

Optional but recommended:
- `disagreement_rate` (float in [0,1])

## Field semantics

- `is_near_tie`: `1` iff `abs_margin <= tie_margin`.
- `tie_margin`: the active near-tie threshold used for margin-band uncertainty.
- `abs_margin`: absolute utility/preference margin for the row's comparison target.
- `utility_std`: estimated std for the compared utility delta.
- `ci_low`, `ci_high`: approximate CI bounds for the utility delta.
- `n_rollouts`: effective rollout sample count used for uncertainty estimation.
- `is_uncertain`: OR-composed uncertainty decision over configured rules.

## Uncertainty rules (OR semantics)

`is_uncertain` is computed with OR semantics over enabled rules:

1. margin-band rule
   - trigger: `abs_margin <= tie_margin`
2. CI-overlap-with-zero rule
   - trigger: `ci_low <= 0 <= ci_high`
3. disagreement-rate rule
   - trigger: `disagreement_rate >= disagreement_rate_threshold`

At least one rule should typically be enabled. Disabling all rules is allowed for ablation/debug but not recommended for canonical runs.

## Slice summaries

Canonical run summaries should include:
- near-tie coverage,
- uncertainty coverage,
- label polarity by budget bucket,
- uncertainty by outside-option type (outside-option rows).

## Framing guardrail

These uncertainty fields are label-quality diagnostics for branch-priority supervision.
They should be interpreted as helper structure under the primary framing:
**next-step branch allocation under fixed budget**.
