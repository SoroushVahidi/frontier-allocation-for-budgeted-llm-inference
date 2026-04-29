# Internal method version audit vs `external_l1_max` (2026-04-29)

## Files inspected
- `scripts/run_cohere_real_model_cost_normalized_validation.py`
- `experiments/frontier_matrix_core.py`
- `docs/BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT_20260429.md`
- `docs/COHERE_DR_V2_TARGETED_FIX_FROM_TRACE_AUDIT_20260429T020000Z.md`
- `docs/COHERE_DR_V2_VS_EXTERNAL_L1_100CASE_VALIDATION_20260429T_COHERE_DR_V2_VS_L1_100CASE.md`
- `docs/METHOD_STATUS_MAP.md`
- `docs/semantic_diversity_expanded_pool_final_decision_snapshot_20260428T143500Z.csv`
- `outputs/l1_better_than_frontier_casebook_20260426T232030Z/summary.json`
- `outputs/internal_method_version_audit_vs_external_l1_20260429/method_version_inventory.csv`

## Direct answers

### Which internal version last beat external_l1_max?
- The clearest named internal hit in Cohere GSM8K budget-4 seed-11 preflight is `direct_reserve_semantic_frontier_v2` at **0.70 vs 0.60** (`+0.10`) in a 10-example slice.

### Was that result small-sample or meaningful?
- **Small-sample only** (n=10), therefore diagnostic/provisional.
- Later evidence in this repo is less favorable: n=20 slice had DR-v2 0.60 vs external 0.70; and the currently completed 100-case subset in the same setting shows DR-v2 0.56 vs external 0.72.

### Which promising variants have not yet been tested at 100 examples?
- In the ongoing DR-v2 100-case timestamp (`20260429T_COHERE_DR_V2_VS_L1_100CASE`), two method slices remain incomplete:
  - `direct_reserve_semantic_frontier_v2_selection_fix_v1`
  - `strict_f3`
- These are runnable and should be finished before any stronger within-run statements.

### Which method should be tested next for the “correct version” hypothesis?
- Prioritize finishing the same timestamp for:
  1. `direct_reserve_semantic_frontier_v2_selection_fix_v1`
  2. `strict_f3`
- Then compare all finalized 100-example slices in the same run (`direct_reserve_semantic_frontier_v2`, selection-fix, external_l1_max, strict_f3).

### Which methods are unsafe because diagnostic-only or not live-runnable?
- `direct_reserve_semantic_frontier_v2_thresholded_ordered`: **not live-runnable** in current runner path; diagnostic-only; should remain excluded from live full comparisons.
- Additional near/calibrated variants are diagnostic evidence in this audit, not manuscript-claim-safe.

### Is `direct_reserve_semantic_frontier_v2_thresholded_ordered` actually runnable?
- **No** for live runner path. It can be registered in method tables, but validation/evidence indicates runtime-missing in `build_frontier_strategies(...)` and therefore excluded from live Cohere full comparisons.

## Inventory output
- Machine-readable inventory: `outputs/internal_method_version_audit_vs_external_l1_20260429/method_version_inventory.csv`
