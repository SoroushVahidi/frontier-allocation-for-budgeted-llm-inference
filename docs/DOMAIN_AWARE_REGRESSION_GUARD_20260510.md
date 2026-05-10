# Domain-Aware Diverse-Anchor Regression Guard

This branch keeps a conservative, no-API scheduling guard available for experimentation, but it is disabled by default after the live 30-case rerun underperformed.

## Behavior

- Watches the diverse-anchor pool after each anchor attempt.
- Triggers only when `direct_l1_anchor` is the current dominant group, the group is weakly supported, diversity has increased, and at least one non-anchor baseline group is still worth preserving.
- Stops additional anchor spending so frontier budget remains available.
- The production diverse-anchor method now runs without this guard unless it is explicitly enabled in configuration or tests.

## Metadata

- `regression_guard_available`
- `regression_guard_enabled`
- `regression_guard_triggered`
- `regression_guard_reason`
- `preserved_candidate_groups`
- `anchor_dominant_selected_group`
- `direct_l1_anchor_dominant`

## Coverage

- Regression case: preserves frontier budget in an `openai_gsm8k_213`-style setup.
- Direct-L1-correct cases: remains non-blocking when the direct-L1 path is already correct.
- Domain-specific anchor improvements: remains non-blocking when a non-direct-L1 anchor develops stronger support.
- PAL protection logic: unchanged.

## Recommendation

- Use `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor` without the regression guard as the default method.
- Only enable the guard explicitly for future controlled experiments.

## Related Triage

- `docs/DOMAIN_AWARE_30CASE_FAILURE_TRIAGE_20260510.md`
- `docs/DOMAIN_AWARE_REGRESSION_GUARD_POSTMORTEM_20260510.md`
