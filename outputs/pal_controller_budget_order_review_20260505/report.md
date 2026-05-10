# Targeted no-API review: `DirectReserveFrontierGateController.run()` ordering + budget

Working dir: ``

Constraints followed:
- no Cohere/HF/OpenAI/API calls
- no live model-evaluation scripts
- no staging/commit

## Scope reviewed

Focused on `experiments/controllers.py`:
- direct reserve phase
- optional seeds: decomp_eq, opcheck, pal, unit_track, direct_hybrid
- frontier remaining-budget handoff
- selector/overlay ordering
- budget metadata fields

Also cross-checked method flags in `experiments/frontier_matrix_core.py` and focused tests in:
- `tests/test_pal_variant.py`
- `tests/test_guarded_k1_frontier4_method.py`
- `tests/test_output_layer_frontier_surfacing.py`
- `tests/test_method_validation_pal_tiebreak_registry.py`

## Key finding

A real budget accounting defect existed in the direct_hybrid path:
- `direct_actions` was incremented by hybrid usage
- but `remaining_budget` was not decremented before frontier construction
- this could over-allocate frontier budget and exceed `max_actions` in edge cases

### Fix applied

In `DirectReserveFrontierGateController.run()` after hybrid seed execution:
- `remaining_budget = max(0, remaining_budget - int(used_here))`
- add metadata: `remaining_budget_after_hybrid_seed`

## Invariant results (post-fix)

- **Seed ordering safety:** deterministic and stable.
- **`max_actions` can be exceeded?** not in reviewed mocked paths after fix; focused test added to enforce.
- **PAL fixed-budget?** yes; `_pal` config sets `pal_budget_actions=1`, and before/after budget metadata now validated.
- **Base k1/tiebreak unchanged?** yes for optional seeds; no PAL/opcheck/decomp/unit metadata emitted in base method.
- **Optional variants interfere?** flags gate them; PAL method explicitly does not emit opcheck/unit/decomp execution metadata.
- **external_l1_max unaffected?** yes (registry test still green).
- **Gold/eval fields used at runtime decisions?** PAL overlay decision uses runtime support/tiebreak metadata, not gold/eval fields.

## Tests added/changed in this review

Updated `tests/test_pal_variant.py` with:
- `test_baseline_k1_tiebreak_has_no_optional_seed_metadata`
- `test_pal_budget_and_frontier_budget_accounting_with_mocked_path`
- `test_pal_skips_seed_when_remaining_budget_is_zero`
- `test_pal_method_does_not_activate_opcheck_or_unit_track_or_decomp_eq`
- `test_direct_hybrid_frontier_budget_respects_max_actions`

## Focused no-API test run

Command:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
.venv/bin/python -m pytest -q \
  tests/test_pal_variant.py \
  tests/test_guarded_k1_frontier4_method.py \
  tests/test_output_layer_frontier_surfacing.py \
  tests/test_method_validation_pal_tiebreak_registry.py
```

Result: **50 passed, 0 failed**.

## Commit/PR readiness

- **Safe to commit/open PR after this targeted fix:** **Yes**, with normal reviewer attention on the large controller diff.
- **Should API run remain blocked until PR merge?**
  - **Technically:** not required; branch behavior is now bounded by tests.
  - **Process/policy:** recommended to wait for PR review/CI before live-cost API runs.

## Artifacts in this review bundle

`outputs/pal_controller_budget_order_review_20260505/`
- `controller_order_summary.json`
- `method_execution_order_table.csv`
- `budget_invariant_checklist.md`
- `controller_risk_notes.md`
- `report.md`
