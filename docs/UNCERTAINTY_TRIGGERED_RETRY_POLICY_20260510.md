# Uncertainty-Triggered Retry Policy 20260510

## Summary

The first live Cohere A/B run for `uncertainty_retry_v1` did not actually exercise the retry stage because the controller reached that decision with no remaining budget. The unstable-feature signals were present, but the retry path reported `no_budget_available`, so the experiment was measuring the scheduling bug rather than the policy.

## Fix

The experimental `uncertainty_retry_v1` controller now reserves one logical action for a possible retry before the normal diverse-anchor loop consumes the full budget.

This keeps production `diverse_anchor` unchanged. The reserve is only enabled on the experimental uncertainty-retry method.

If the uncertainty features do not justify a retry, the reserved action is released back to the frontier budget and recorded in metadata. If the budget is too small to hold a reserve, the controller reports that clearly in metadata.

## Metadata

The retry controller now records:

- `uncertainty_retry_reserved_budget`
- `uncertainty_retry_budget_reserved`
- `uncertainty_retry_budget_released`
- `uncertainty_retry_budget_unused`
- `remaining_budget_before_uncertainty_retry`
- `remaining_budget_after_uncertainty_retry`

The existing uncertainty metadata fields remain in place:

- `uncertainty_retry_enabled`
- `uncertainty_retry_triggered`
- `uncertainty_retry_reason`
- `uncertainty_retry_target_anchor_id`
- `uncertainty_retry_extra_attempts`
- `uncertainty_retry_features`

## Validation status

This is a no-API fix. It should be validated with local tests first, then with a new live diagnostic run later.

No new Cohere/OpenAI/Gemini/Anthropic calls were made for this change.
