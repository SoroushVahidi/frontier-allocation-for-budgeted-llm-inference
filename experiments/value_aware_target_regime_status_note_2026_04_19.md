# Value-aware target regime bounded comparison (2026-04-19)

Implemented a budget-conditioned target layer with Q_commit/Q_expand plus regret/gap fields,
ambiguity buckets, and a value-aware defer option; then ran matched comparisons across 4 methods.

Key artifacts:
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/aggregate_comparison.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/per_method_metrics.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/hard_slice_diagnostics.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/ambiguity_bucket_diagnostics.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/defer_label_audit.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/defer_score_audit.json
- outputs/branch_label_bruteforce_learning/value_aware_defer_audit_20260419_pass3/defer_per_example_scores_decomposed.json

Interpretation discipline:
- This is a bounded mock-permitted run for pipeline hardening and supervision semantics checks.
- Treat gains/losses as directional until replayed on larger exact-heavy state sets.
