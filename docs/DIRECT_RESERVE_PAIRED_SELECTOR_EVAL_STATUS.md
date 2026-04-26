# Direct Reserve Paired Selector Eval Status

## Why prior comparison was not interpretable

The earlier tiny real comparison mixed independent stochastic method runs. It did not contain paired `direct_reserve_strong_plus_diverse_learned_override_v1` rows on the same candidate pools as base plus-diverse, so the apparent degradation could not be attributed to selector behavior.

## Paired-candidate-pool principle

This evaluation uses one candidate pool per case (from `direct_reserve_strong_plus_diverse_v1` rows in `candidate_branch_table.csv`) and applies multiple selectors offline to that same pool:

- base plus-diverse selector,
- support-count selector,
- learned RF selector with thresholded override,
- optional margin-gated reference (when present in per-case metadata).

No API calls are required for paired selector evaluation.

## Fresh artifact search result

Inventory file:

- `outputs/direct_reserve_paired_selector_repair_20260426T_REPAIR/fresh_artifact_inventory.csv`

Findings:

- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/` exists and is the first slice.
- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z/` exists and shows overlap count `20` with first slice.
- `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T_FRESH_GSM8K_SCORER_VALIDATION/` is not present in this checkout.

So the true fresh zero-overlap package is currently missing here; `151700Z` must be treated as `overlapping_validation`, not fresh.

## Candidate pools evaluated

- First slice:
  - `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/`
- Overlap diagnostic (not fresh):
  - `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z/`

## Model path and portability/retraining policy

Requested model path:

- `outputs/direct_reserve_candidate_scorer_train_20260426T150000Z/selected_model.joblib`

In this environment, loading this pickle fails with:

- `ValueError("<class 'numpy.random._pcg64.PCG64'> is not a known BitGenerator module.")`

Paired eval now has explicit policy:

1. try load model;
2. record load error if incompatible;
3. retrain only when `--allow-retrain-on-load-failure` is enabled.

For these runs, fallback retraining was enabled and wrote:

- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_FIRST/retrained_model.joblib`
- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/retrained_model.joblib`

Each run also writes:

- `retrained_model_manifest.json`
- `feature_schema_used.json`
- `training_dataset_path.txt`

HGB is not used by default.

## Repaired paired-eval results (margin-only)

### First slice (`20260426T_REPAIRED_FIRST`, source_type=`first_slice`)

- base selected-gold rate: `0.60`
- support-count selected-gold rate: `0.60`
- learned selected-gold rate:
  - `t=0.00`: `0.75` (8 overrides, 5 improvements, 2 degradations, 1 control degradation)
  - `t>=0.02`: `0.60` (0 overrides)
- best threshold by selected-gold rate: `0.00`

### Overlap diagnostic (`20260426T_REPAIRED_OVERLAP_DIAGNOSTIC`, source_type=`overlapping_validation`)

- base selected-gold rate: `0.80`
- support-count selected-gold rate: `0.80`
- learned selected-gold rate:
  - `t=0.00`: `0.60` (6 overrides, 1 improvement, 5 degradations, 3 control degradations)
  - `t>=0.02`: `0.80` (0 overrides)
- best threshold by selected-gold rate: `0.02` (ties at zero overrides)

## Policy sweep (same candidate pools, diagnostic)

Policy outputs:

- `outputs/direct_reserve_paired_selector_policy_sweep_20260426T_REPAIRED_FIRST/`
- `outputs/direct_reserve_paired_selector_policy_sweep_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/`

Observations:

- On first slice, permissive policies at `t=0.00` improve accuracy but still introduce degradations (including control degradation).
- On overlap diagnostic, permissive policies at `t=0.00` degrade strongly.
- Conservative thresholds (`>=0.02`) generally collapse to no overrides in both slices.
- `margin_plus_cross_method` avoids risky overrides here but also provides no gain (0 overrides in these artifacts).

## Readiness

- Learned override remains diagnostic-only.
- Paired evaluator is now interpretable and explicitly labels overlap vs fresh.
- True fresh zero-overlap evidence is still missing in this checkout; overlap runs are not fresh-generalization evidence.
- Recommendation: recover the true fresh package (or regenerate it later in a separate real-call task) before making usefulness claims from paired selector behavior.

