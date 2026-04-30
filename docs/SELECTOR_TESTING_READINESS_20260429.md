# Selector Testing Readiness (2026-04-29)

- Implemented selectors:
  - `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` (live-runnable)
  - `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` (live-runnable)
- Default verifier backend is `mock` unless env overrides are set.

## Required Cohere env vars
- `DR_V2_OV_RERANK_VERIFIER_BACKEND=cohere`
- `DR_V2_OV_RERANK_COHERE_MODEL=command-r-plus-08-2024`
- `DR_V2_PRM_STEP_VERIFIER_BACKEND=cohere`
- `DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL=command-r-plus-08-2024`

## What changed for selector surface
- Added robust shared candidate extraction across keys (`selector_candidate_pool`, `final_branch_states`, `branch_states`, `final_nodes`, `candidate_answers`, `answer_groups`) with explicit extraction-source metadata.
- Controllers now emit `candidate_extraction_sources` and carry forward `selector_candidate_pool` from `final_branch_states` when present.
- Added run-level selector candidate surface diagnostic script to summarize candidate/rerank/fallback distributions and missing metadata fields.

## Current gating for full Wulver selector run
A full run is worthwhile only when tiny/local diagnostics show:
1. `candidate_count > 1` for a non-trivial fraction of selector rows,
2. `*_rerank_applied=True` appears in rows,
3. fallback reason is not dominated by `single_candidate_only`.

Active-run evidence noted by user still indicates single-candidate fallback; run `scripts/diagnose_selector_candidate_surface.py` on the target run folder before scaling.
