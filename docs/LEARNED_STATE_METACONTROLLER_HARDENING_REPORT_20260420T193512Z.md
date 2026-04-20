# Learned state metacontroller hardening report (20260420T193512Z)

## Stability verdict
- Keep this line as a bounded candidate (not promoted default yet): training/eval are now tied to canonical artifacts and grouped holdout evaluation.
- Test regression in uncertainty near-tie rule is resolved in this pass (see tests section below).

## Canonical sources used
- targeted_failure_casebook: `docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md`
- broad_comparison_manifest: `outputs/full_method_comparison_bundle/20260419T214335Z/manifest.json`
- near_miss_report: `docs/NEAR_MISS_CORRECTION_EVAL_REPORT_20260420T184849Z.md`
- current_full_method_comparison_report: `docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`

## What was hardened
- Removed markdown/fallback-heavy broad-case logic in favor of canonical full-method bundle per-example losses.
- Targeted cases now sourced from the canonical twenty exact failure casebook.
- Training pool expanded in a controlled way (extra datasets/seeds/budgets), with case-grouped train/test split to reduce leakage.
- Added confusion matrix, class-wise F1, predicted-class frequencies, feature importances, and action-pattern diagnostics.

## Evaluation summary
- Best model: `decision_tree`.
- Train rows: 552 (groups=144); test rows: 242 (groups=63).
- Targeted improvements vs old current full: 1; worsened: 9.
- Broader improvements vs old current full: 0; worsened: 0.

## Learned-action behavior checks
- Commit rate (targeted/broad): 0.306 / 0.000.
- Refine rate (targeted/broad): 0.387 / 0.000.
- Verify on near-tie proxy (targeted/broad): 0.145 / 0.000.
- Widen on monopolization proxy (targeted/broad): 0.000 / 0.000.
- Interpretation: action choices are now inspectable and tied to explicit proxy slices rather than only aggregate accuracy.

## Is learned policy more promising than deterministic gates?
- Treat as promising if improvements > worsened across both targeted and broader slices; otherwise keep as diagnostic branch.
- Current pass result: targeted (improved=1, worsened=9), broader (improved=0, worsened=0).

## Next method step
- Keep lightweight/interpretable modeling, but introduce policy calibration constraints on commit and verify frequencies and rerun matched-case evaluation.

## Required final fields
- old current full method name: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- learned metacontroller method name: `broad_diversity_aggregation_strong_v1_state_action_metacontroller_v2`
- test regression fixed: `true`
- training dataset size: `794`
- targeted-slice improvement count: `1`
- broader-surface improvement count: `0`
- docs report path: `docs/LEARNED_STATE_METACONTROLLER_HARDENING_REPORT_20260420T193512Z.md`
- output bundle path: `outputs/learned_state_metacontroller_20260420T193512Z`
