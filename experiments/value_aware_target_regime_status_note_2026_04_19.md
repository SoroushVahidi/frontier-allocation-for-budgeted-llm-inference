# Value-aware target regime bounded comparison (2026-04-19)

Implemented a budget-conditioned target layer with Q_commit/Q_expand plus regret/gap fields,
ambiguity buckets, and a value-aware defer option; then ran matched comparisons across 5 methods.

Key artifacts:
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/aggregate_comparison.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/per_method_metrics.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/hard_slice_diagnostics.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/ambiguity_bucket_diagnostics.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/defer_label_audit.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/defer_score_audit.json
- outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v3/defer_per_example_scores_decomposed.json

Interpretation discipline:
- This is a bounded mock-permitted run for pipeline hardening and supervision semantics checks.
- Treat gains/losses as directional until replayed on larger exact-heavy state sets.

Status answers (bounded evidence, no broad claims):
- Did continuation-minus-commit reduce supervision bottleneck? **Partially yes** in this bounded run: supervision now includes `Q_commit`, per-branch `Q_expand`, `A_expand_minus_commit`, regret/gap fields, ambiguity buckets, and reliability fields.
- Improve expand-vs-commit? **Yes directionally**: baseline `expand_vs_commit_accuracy_test=0.50` and `mean_regret=0.1246`; value-aware+ambiguity variants reached `1.00` and `0.0`.
- Improve branch ranking? **Yes on pairwise slices**: baseline `pairwise_accuracy_test=0.5714`; value-aware+ambiguity variants reached `0.8571`. Top-1 ranking stayed `1.00` across methods in this tiny matched run.
- Improve hard ambiguous states? **Yes directionally on near ties**: `near_tie_pairwise_accuracy_test` moved from `0.0` to `0.6667` for ambiguity-aware methods.
- Is target variance unresolved? **Still partly unresolved**: paired rollouts + repeated estimation + reliability weighting reduced brittleness, but this remains an open risk requiring larger exact-heavy confirmation.
- Best next step: run this matched protocol on larger exact-heavy state sets, then tune ambiguity-band weighting and defer thresholds separately for near-tie vs far-margin regimes.
