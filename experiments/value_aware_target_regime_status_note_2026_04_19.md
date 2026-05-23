# Value-aware target regime bounded comparison (2026-04-19)

Implemented a budget-conditioned target layer with Q_commit/Q_expand plus regret/gap fields,
ambiguity buckets, and a value-aware defer option; then ran matched comparisons across 4 methods.

Key artifacts:
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/aggregate_comparison.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/per_method_metrics.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/hard_slice_diagnostics.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/ambiguity_bucket_diagnostics.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_label_audit.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_score_audit.json
- /tmp/pytest-of-soroush/pytest-450/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_per_example_scores_decomposed.json

Interpretation discipline:
- This is a bounded mock-permitted run for pipeline hardening and supervision semantics checks.
- Treat gains/losses as directional until replayed on larger exact-heavy state sets.

Status answers (bounded evidence, no broad claims):
- Did continuation-minus-commit reduce supervision bottleneck? Partially: richer value targets, gap/regret/reliability fields, and ambiguity buckets are now directly supervised.
- Improve expand-vs-commit? Check aggregate_comparison expand_vs_commit_accuracy_test and regret fields vs baseline.
- Improve branch ranking? Check ranking_top1_accuracy_test and pairwise_accuracy_test by method/slice.
- Improve hard ambiguous states? Check near_tie_* and ambiguity_bucket_diagnostics.json; report mixed if unstable.
- Is target variance unresolved? Reduced via paired rollouts + repeated estimation + reliability weighting, but still a tracked risk.
- Best next step: run the same matched protocol on larger exact-heavy state sets and tune ambiguity-band weighting per regime.
