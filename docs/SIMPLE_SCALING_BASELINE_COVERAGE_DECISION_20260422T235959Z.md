# Simple scaling baseline coverage decision (20260422T235959Z)

Decision: **The current direct package already covers the simple inference-time scaling axis; no new baseline was added.**

## Why this is reviewer-defensible
- `external_s1_budget_forcing` is already integrated as a near-direct inference-time budget-forcing baseline on the matched substrate.
- The canonical ranking also includes `self_consistency_3` as internal context for Best-of-N/self-consistency behavior.
- Adding another lightweight self-consistency/Best-of-N baseline in this pass would be redundant and risk baseline sprawl instead of improving fairness clarity.

## Scope boundary
- This decision is limited to **inference-only adapter** comparability in this repository.
- It is **not** a claim of full official s1 post-training reproduction.

## Artifacts
- `outputs/simple_scaling_baseline_coverage_audit/20260422T235959Z/coverage_decision.json`
- `outputs/simple_scaling_baseline_coverage_audit/20260422T235959Z/coverage_decision.md`
- `outputs/simple_scaling_baseline_coverage_audit/20260422T235959Z/direct_baseline_role_matrix.csv`
- `outputs/paper_facing_baseline_tables/20260422T231500Z/simple_scaling_axis_explicit_note.md`
