# Results And Artifacts Guide

## Direct reserve scorer slices

- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/`
  - class: `first_slice`
  - status: valid paired-eval input
- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z/`
  - class: `overlapping_validation`
  - status: overlaps first slice (`20` overlap), **not fresh**
- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T_FRESH_GSM8K_SCORER_VALIDATION/`
  - class: `true_fresh_zero_overlap`
  - status in this checkout: missing

## Paired selector diagnostics (non-canonical)

- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_FIRST/`
- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/`
- `outputs/direct_reserve_paired_selector_policy_sweep_20260426T_REPAIRED_FIRST/`
- `outputs/direct_reserve_paired_selector_policy_sweep_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/`

These are diagnostic-only selector studies on same candidate pools. They are not canonical paper artifacts.

## Fresh artifact inventory

- `outputs/direct_reserve_paired_selector_repair_20260426T_REPAIR/fresh_artifact_inventory.csv`

Use this inventory to verify whether a package is truly fresh zero-overlap before interpreting paired selector results as fresh-generalization evidence.

