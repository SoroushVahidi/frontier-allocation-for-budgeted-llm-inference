# Selector Catalog

## Deployable selectors (current)
- `direct_reserve_semantic_frontier_v2`
- `direct_reserve_semantic_frontier_v2_selection_fix_v1`
- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`
- `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`

## Offline diagnostics (non-deployable)
- `oracle_answer_selector` (gold-aware ceiling)
- `support_only_selector`
- `consistency_penalized_selector`
- `unified_confidence_selector`
- `hybrid_support_confidence_consistency_selector`

## Transfer policy
- Reuse consistency/error/confidence diagnostics from `-adaptive-llm-inference`.
- Do **not** reuse binary route/revise policy methods as current runtime methods.
