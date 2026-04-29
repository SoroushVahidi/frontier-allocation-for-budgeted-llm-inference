# Real-model internal method audit (2026-04-29)

## Most important audit conclusions
1. **Manuscript-facing matched internal winner:** `strict_f3`.
2. **Broader operational default:** `strict_gate1_cap_k6`.
3. **Newer/diagnostic variants not included in PR #304’s registered subset:** `strict_f3_anti_collapse_weak_v1`, `direct_reserve_semantic_frontier_v1`, `direct_reserve_semantic_frontier_v2_selection_fix_v1`, `direct_reserve_semantic_frontier_v2_thresholded_ordered`, `near_direct_reserve_frontier_gate_v1`, `calibrated_near_direct_frontier_gate_v1`.
4. **Implemented + safe to expose in the real-model runner:** all above except adapters without stable method IDs; `direct_reserve_semantic_frontier_v2_thresholded_ordered` was implemented and is now registered in the runner.
5. **Diagnostic-only/obsolete not to promote as canonical default:** `strict_f3_anti_collapse_weak_v1`, DR-v2 thresholded/ordered, near-direct and calibrated-near-direct variants (diagnostic evidence only).
6. **PR #304 scope:** tested only the then-registered runner subset, not all implemented internal variants in core/diagnostic registries.

## Audit scope and evidence
- Runner registry: `scripts/run_cohere_real_model_cost_normalized_validation.py`.
- Core implementations: `experiments/frontier_matrix_core.py`, `experiments/controllers.py`, `experiments/semantic_diversity_diagnostic_strategies.py`.
- Positioning docs reviewed: `docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`, `docs/PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md`, `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`.

## Registered/runnable summary
- **Internal registered+runnable:** `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `strict_f3_anti_collapse_weak_v1`, `direct_reserve_semantic_frontier_v1`, `direct_reserve_semantic_frontier_v2`, `direct_reserve_semantic_frontier_v2_selection_fix_v1`, `near_direct_reserve_frontier_gate_v1`, `calibrated_near_direct_frontier_gate_v1`, `direct_reserve_semantic_frontier_v2_thresholded_ordered` (added).
- **External registered+runnable aliases:** `external_l1_max`, `tale` -> `external_tale_prompt_budgeting`, `s1` -> `external_s1_budget_forcing`, `self_consistency_3`.
- **Audited but not registered in this runner:** `external_l1_exact`, `tot_beam_matched_budget`, `verifier_guided_search` (implemented in core but not in `METHODS`).
- **Not implemented/runnable method IDs:** `self_consistency_5`, BEST-Route-style adapter ID, difficulty-proxy adapter ID.

See detailed row-level status in `docs/real_model_internal_method_audit_20260429.csv`.
