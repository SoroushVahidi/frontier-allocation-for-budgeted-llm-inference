# Port / fix plan — restore real PAL in the clean branch (minimal, no outputs)

## Situation

Classification **C**: **real PAL is absent from `research-next-wt`** (and absent from `pal-pilot-clean` / `diverse-root-clean`), but **exists locally** under `` with:

- sandbox execution helper `experiments/pal_executor.py`
- controller wiring (`enable_pal_branch`, `pal_budget_actions`, `_run_pal_seed_attempt`, metadata emission)
- output-layer normalization / integration overlays in `experiments/output_layer_repair.py`
- `experiments/frontier_matrix_core.py` PAL kwargs bundle for **`...FRONTIER_TIEBREAK_PAL`**
- PAL-focused tests + `scripts/materialize_pal_smoke_summary.py`

This audit **did not apply** those changes.

## Minimal port checklist (preferred order)

1. **`experiments/pal_executor.py`**  
   Copy from main checkout verbatim; verify imports are stdlib-only inside executor (should remain API-free for unit tests).

2. **`experiments/controllers.py`** (surgical merge)  
   Port the **`DirectReserve...` PAL seed path**: imports from `experiments.pal_executor`, constructor kwargs (`enable_pal_branch`, `pal_budget_actions`, `pal_selection_policy` if referenced), **`_run_pal_seed_attempt`**, and any **`pal_execution` / `pal_overlay` metadata shaping** reachable from diverse-root guarded runs.  
   **Avoid** wholesale file replacement (~9k LOC); prefer `git diff` chunks between main checkout and `research-next-wt` limited to PAL-tagged regions.

3. **`experiments/output_layer_repair.py`**  
   Port **PAL integration / normalization** functions that materialization expects (`pal_execution`, `pal_overlay` idempotency, `pal_integration_*` fields). Without this, even correct controller metadata may not surface consistently.

4. **`experiments/frontier_matrix_core.py`**  
   Replace the current labelled-duplicate **`...FRONTIER_TIEBREAK_PAL`** spec kwargs with **`strategy_seeded_outer_kwargs_k1_frontier4_pal`** matching main checkout:
   - `enable_pal_branch=True`
   - `pal_budget_actions=1`
   - `pal_selection_policy="weak_frontier_or_supported_agreement"`  
   Confirm imports/constants align (main checkout also had additional variants like **`...TIEBREAK_OPCHECK`**; bring **only** what PAL depends on).

5. **`experiments/strategy_seeded_semantic_diversity_frontier_v1.py`**  
   Confirm `METHOD_*` constants match main for any ported variants; no change if constants already aligned.

6. **`scripts/run_cohere_real_model_cost_normalized_validation.py`**  
   Registry entry for `_pal` should remain; after port, validate that runtime id still maps to **`build_frontier_strategies`** key.

7. **Tests / tooling (recommended, still minimal)**  
   - Add `tests/test_pal_executor.py`, `tests/test_pal_variant.py`, `tests/test_pal_smoke_postprocess.py` from main checkout.  
   - Add `scripts/materialize_pal_smoke_summary.py` if reviewers rely on smoke summaries.

8. **Do not port:** `outputs/**`, caches, HF artifacts, `.env`.

## Verification gate (before any larger paired Cohere run)

Run the PAL-specific tests plus JSON parse/surfacing tests; then:

`scripts/run_cohere_real_model_cost_normalized_validation.py ... --validate-methods-only`

Additionally (post-port): assert controller construction kwargs for **`..._tiebreak_pal`** expose `enable_pal_branch=True` in a narrow unit/integration test.
