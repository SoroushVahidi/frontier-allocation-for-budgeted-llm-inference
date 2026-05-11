# Uncertainty-Triggered Retry Policy Scaffold

This note documents the next no-API algorithmic branch after the domain-gated stability experiment.

## Why This Direction

The earlier `stability_redundant_anchor_v1` line was validated as an internal experiment, not as a recommended default.
The clean budget-4 A/B rerun for the gated stability policy showed that blanket or domain-gated redundancy was not reliable enough for broad use.

The next step is therefore a lighter-weight, selective policy:

- retry only when the candidate pool looks unstable;
- avoid spending extra budget when the pool already looks confident;
- keep the production `diverse_anchor` method unchanged.

## Status

- Default production behavior remains unchanged.
- The new policy is disabled by default in the recommended method.
- The new policy is only enabled through an experimental method wiring.
- This is a no-API scaffold, not a live accuracy claim.

## Experimental Method

The experimental method ID is:

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1`

It keeps the domain-aware diverse-anchor setup, but turns on the uncertainty retry scaffold:

- `enable_diverse_anchor_uncertainty_retry_policy=True`
- `diverse_anchor_uncertainty_retry_policy="uncertainty_triggered_retry_v1"`
- `diverse_anchor_uncertainty_retry_extra_anchor_attempts=1`

## Trigger Features

The policy uses cheap candidate-pool features only:

- low support for the incumbent answer group
- high disagreement / high entropy
- too few answer groups in the candidate pool
- direct-L1-dominant but weak candidate behavior
- domain-specific anchor disagreement
- parse or surfacing warnings such as `model_step_missing`

If those signals do not point to instability, the policy does not spend extra budget.

## Domain Targeting

When the policy triggers and budget allows, it retries using the most appropriate anchor:

- `multi_step_arithmetic` -> `backward_check_anchor` or `equation_first_anchor`
- `ratio_percent` -> `ratio_percentage_anchor`
- `money_cost_revenue` -> `unit_ledger_money_anchor` or `equation_first_anchor`

## Metadata

The policy records:

- `uncertainty_retry_policy`
- `uncertainty_retry_enabled`
- `uncertainty_retry_triggered`
- `uncertainty_retry_reason`
- `uncertainty_retry_target_anchor_id`
- `uncertainty_retry_budget_available`
- `uncertainty_retry_features`
- `uncertainty_retry_extra_attempts`

## Safety / Cost Behavior

- If the policy is disabled, it is a no-op.
- If the policy is enabled but confidence is sufficient, no extra action is spent.
- If the policy is enabled but no budget is left, the metadata records that clearly and the retry is skipped.
- The production `diverse_anchor` path is not changed.

## What This Is Not

- Not a replacement for the current recommended method.
- Not a claim that the retry policy improves live accuracy yet.
- Not a prompt to expand the old stability-redundancy line.

## Recommended Current Method

The recommended current method remains:

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`

`stability_redundant_anchor_v1` remains experimental/internal only.

## Future Cohere Diagnostic Design

If this scaffold is later evaluated live, the next diagnostic should:

- keep the same exact-case replay set;
- compare the baseline diverse-anchor method against the uncertainty-retry treatment;
- focus first on budget-4 only;
- measure whether retries recover unstable cases without harming the stable ones;
- only expand to larger budgets after the cheap gate behavior looks clean.
