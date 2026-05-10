# Runtime wiring audit

## Scope
Implemented production-equivalent v1 runtime hook wiring for:
- bounded targeted retry (max 1 extra call by default)
- final answer surface parity source metadata

## Inspected integration points
- experiments/controllers.py
- experiments/frontier_matrix_core.py
- experiments/strategy_seeded_semantic_diversity_frontier_v1.py
- experiments/output_layer_repair.py
- experiments/targeted_discovery_retry.py
- experiments/adaptive_retry_router.py
- experiments/final_target_verifier.py
- scripts/run_cohere_real_model_cost_normalized_validation.py
- scripts/run_production_equivalence_stage3_dry_run.py
- tests/test_production_equivalence_stage3.py

## Wiring decisions
- New behavior is opt-in via alias `..._production_equiv_v1` only.
- Existing methods/aliases unchanged.
- Runtime hook uses router v3 + final-target verifier features to choose/validate retry.
- Allowed retry scaffolds constrained to validated list only.
- Discovery3 patch excluded and percent-base disabled by default.
- Metadata contract fields emitted for production-equivalent surface provenance.

## Implementation status
- `controller_runtime_targeted_retry_loop_not_fully_wired`: resolved for production_equiv_v1 alias path.
- `controller_surface_parity_source_not_fully_wired`: resolved at controller metadata level via explicit `production_equiv_surface_source` and reason fields.

## Remaining cautions
- No-API dry-run validates planning/metadata contract only; live behavior still requires explicit tiny smoke before larger checkpoint.
