# Budget invariant checklist

- [x] **Total logical actions bounded by `max_actions`** in focused mocked paths.
  - Added `test_pal_budget_and_frontier_budget_accounting_with_mocked_path`.
  - Added `test_direct_hybrid_frontier_budget_respects_max_actions`.
- [x] **Base non-PAL K1/tiebreak unchanged** (no optional-seed metadata emitted).
  - Added `test_baseline_k1_tiebreak_has_no_optional_seed_metadata`.
- [x] **Optional seed only runs when method flag is enabled.**
  - PAL method now asserted to exclude opcheck/unit/decomp metadata.
- [x] **PAL fixed-budget behavior (`pal_budget_actions=1`)** verified in mocked budget path.
- [x] **Frontier budget never negative.**
  - Controller uses `remaining_budget = max(0, remaining_budget - observed)` across optional seeds.
- [x] **No optional seed after frontier budget is exhausted.**
  - Added `test_pal_skips_seed_when_remaining_budget_is_zero`.
- [x] **Overlay order deterministic** in `run()` source order:
  1. frontier max-support tiebreak
  2. direct_hybrid overlay
  3. opcheck overlay
  4. decomp_eq overlay
  5. pal overlay
  6. unit_track overlay
- [x] **external_l1_max unaffected.**
  - Existing registry tests remain green.
- [x] **No gold/eval fields in runtime PAL overlay decisions.**
  - PAL overlay calls `decide_pal_strong_overlay_promotion(...)` with support/tiebreak/runtime metadata only.

## issue found + fixed during this review

- **Found:** direct_hybrid path incremented `direct_actions` but did not decrement `remaining_budget` before frontier creation, allowing frontier to receive a stale budget cap.
- **Fix applied:** in `DirectReserveFrontierGateController.run()`, after hybrid seed execution:
  - decrement `remaining_budget` by `used_here`;
  - record `remaining_budget_after_hybrid_seed` in `direct_hybrid_seed_execution` metadata.
- **Validation:** focused suite passed after fix.
