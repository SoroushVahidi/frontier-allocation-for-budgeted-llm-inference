# Outputs directory guide

This directory stores generated artifacts from scripts and evaluation passes.

## Current-canonical output families

Use these first for current claims:

### 1. Current broad comparison / ranking
- `current_full_method_comparison_bundle_20260420/`

### 2. Current exact loss surface
- `twenty_exact_current_full_vs_best_fresh_20260420/`

### 3. Current output-layer repair analysis
- `current_failure_output_layer_repair_20260420/`

### 4. Current targeted method-development surfaces
- `twenty_exact_current_full_improvement_eval_20260420T181131Z/`
- `targeted_failure_bundle_20260420T183801Z/`
- `near_miss_correction_eval_20260420T184849Z/`

## Historical or bounded paper-facing output families

These are still useful, but they are not the default current ranking source:
- `imported_methodology_frontier_eval/`
- `paper_plot_data/`
- older `full_method_comparison_bundle/` runs that predate the current April 20 broad comparison path

## Interpretation rule

- Do not use an output folder as a headline evidence source unless it is linked from the current canonical docs.
- Check `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md` and `docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md` before using a folder for manuscript claims.
