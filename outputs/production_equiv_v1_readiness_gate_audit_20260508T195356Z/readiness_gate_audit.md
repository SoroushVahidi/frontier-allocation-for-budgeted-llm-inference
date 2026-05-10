# Readiness gate audit

## Observed inconsistency
- remaining_blocking_issues: []
- ready_for_tiny_live_smoke: False
- ready_for_live_50_checkpoint: False

## Root cause
The dry-run script used conservative hard-coded flags:
- `ready_for_tiny_live_smoke=False`
- `ready_for_live_50_checkpoint=False`
Even when `runtime_targeted_retry_hook_wired=True`, `surface_parity_source_wired=True`, and blockers were empty.

## Policy fix applied
Updated dry-run readiness logic:
- `ready_for_tiny_live_smoke = runtime_targeted_retry_hook_wired and surface_parity_source_wired and len(remaining_blocking_issues)==0`
- `ready_for_live_50_checkpoint` remains `False` by policy until tiny live smoke pass.

## Safety note
This change adjusts readiness reporting only. It does not alter fair-baseline settings, discovery3 exclusion defaults, or percent-base default behavior.
