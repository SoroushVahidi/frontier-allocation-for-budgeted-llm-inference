# Controller risk notes

## High-priority observation

`experiments/controllers.py` has broad changes in one hot method (`DirectReserveFrontierGateController.run()`), combining multiple optional seeds into a shared path. This increases regression surface even when each seed is gated by flags.

## Confirmed risk resolved in this review

- **Direct-hybrid stale remaining budget** was real and reproducible with a deterministic test.
- Patched and covered by test.

## Remaining medium risks

1. **Ordering coupling risk**
   - Optional seeds are ordered decomp -> opcheck -> pal -> unit_track -> direct_hybrid(pre-frontier overlay stage after tiebreak).
   - Future changes to ordering can silently affect final answer arbitration.
2. **Metadata fan-out complexity**
   - Many similarly named fields (`frontier_budget_before_*`, `frontier_budget_after_*`, `*_budget_cost_observed`) can drift.
3. **Selector/overlay interactions**
   - Overlay precedence is deterministic but non-trivial; maintain tests for precedence whenever adding a new seed.

## Suggested guardrails before merge

- Keep the new focused tests in CI.
- Prefer adding one invariant-style test per future optional seed.
- Document overlay precedence in code comments near overlay block.
