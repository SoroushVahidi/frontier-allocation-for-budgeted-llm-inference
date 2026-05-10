# Integration point audit

## Inspected files
- experiments/frontier_matrix_core.py
- experiments/strategy_seeded_semantic_diversity_frontier_v1.py
- experiments/controllers.py
- experiments/output_layer_repair.py
- experiments/adaptive_retry_router.py
- experiments/final_target_verifier.py
- experiments/targeted_discovery_retry.py
- scripts/run_cohere_real_model_cost_normalized_validation.py
- scripts/run_production_equivalence_stage3_dry_run.py
- tests/test_production_equivalence_stage3.py
- tests/test_integrated_structural_targeted_retry_v1.py

## Key integration findings
- Runtime aliases are registered in `strategy_seeded_semantic_diversity_frontier_v1.py`, then imported and materialized in `frontier_matrix_core.py` strategy specs.
- Method exposure for validation CLI is controlled by `METHODS` in `run_cohere_real_model_cost_normalized_validation.py`.
- Structural commitment runtime flag is already supported by `DirectReserveDiverseRootFrontierV1GuardedController` via `enable_structural_commitment_v1`.
- Controller metadata already contains rich parity context (`final_answer`, `frontier_*`, `selector_candidate_pool`, PAL overlays), enabling production-equivalent metadata plumbing without live API calls.
- Adaptive router v3 and final-target verifier v1 are deterministic/offline and safe for dry-run planning.
- Existing production-equivalence dry-run existed but used older alias/file contract; required v1 contract-specific output names and metadata keys were missing.

## Design decisions for production_equiv_v1
- New alias is opt-in and mapped to guarded+PAL+structural commit base runtime only; old aliases preserved.
- Discovery3 patch is explicitly excluded by config default and dry-run metadata (`production_equiv_excluded_patches`).
- Percent-base denominator remains disabled by default.
- Targeted retry scaffolds restricted to validated set only:
  - quantity_ledger_v2_1
  - rate_table_v1
  - before_after_state_v1
  - target_difference_v1
  - final_target_extraction_repair
  - l1_style_concise_decomposition
- Dry-run emits explicit blocking hooks when full runtime controller loop/surface parity is not yet fully wired.

## Remaining runtime blockers
- Controller-level bounded targeted-retry execution hook is still scaffolded/planned rather than fully composed in a dedicated production-equivalent runtime path.
- Production surface parity source labeling across runtime/evaluator layers needs a final live-path handshake.
