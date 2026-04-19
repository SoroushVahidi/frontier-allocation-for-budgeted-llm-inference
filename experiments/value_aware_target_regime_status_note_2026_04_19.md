# Value-aware target regime bounded comparison (2026-04-19)

Implemented a budget-conditioned target layer with Q_commit/Q_expand plus regret/gap fields,
ambiguity buckets, and a value-aware defer option; then ran matched comparisons across 4 methods.

Key artifacts:
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/aggregate_comparison.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/per_method_metrics.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/hard_slice_diagnostics.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/ambiguity_bucket_diagnostics.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_label_audit.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_score_audit.json
- /tmp/pytest-of-root/pytest-0/test_defer_threshold_sweep_art0/pytest_defer_threshold_sweep/defer_per_example_scores_decomposed.json

Interpretation discipline:
- This is a bounded mock-permitted run for pipeline hardening and supervision semantics checks.
- Treat gains/losses as directional until replayed on larger exact-heavy state sets.
