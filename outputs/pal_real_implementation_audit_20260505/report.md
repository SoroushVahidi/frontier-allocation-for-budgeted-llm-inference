## PAL real implementation audit — summary

- **Classification:** **C**
- **`..._tiebreak_pal` in clean worktree today:** **`METHODS`/spec resolve, but runtime is still the labelled duplicate of plain tiebreak (`enable_pal_branch` absent)** → **not real PAL behavior.**
- **Where PAL actually exists:** **only in the dirty local checkout** `` (not merged into `research-next-wt`; `pal-pilot-clean` / `diverse-root-clean` were also missing PAL executor + PAL controller flags).

### Fix applied?

**None** (audit + artifacts only).

### Minimal port targets (exact files)

1. `experiments/pal_executor.py` *(new)*  
2. `experiments/controllers.py` *(PAL-aware diverse-root/direct-reserve path + metadata)*  
3. `experiments/output_layer_repair.py` *(PAL extraction / overlay / integration sidecars)*  
4. `experiments/frontier_matrix_core.py` *(replace TIEBREAK_PAL kwargs with `..._pal` bundle: `enable_pal_branch=True`, `pal_budget_actions`, `pal_selection_policy`, etc.)*  
5. Tests: `tests/test_pal_executor.py`, `tests/test_pal_variant.py`, `tests/test_pal_smoke_postprocess.py` *(plus `tests/test_output_layer_frontier_surfacing.py` if ported from main—it is absent here)*  
6. Optional tooling: `scripts/materialize_pal_smoke_summary.py`

### Tests (requested)

- Missing PAL-focused tests/scripts in clean worktree → **not runnable**.  
- Subset executed: **`tests/test_method_validation_pal_tiebreak_registry.py` + `tests/test_api_branch_generator_json_parsing.py` → `29 passed`**.

### `--validate-methods-only`

- **PASS** (`validated_rows=2 bad_rows=0`, report under `outputs/cohere_real_model_cost_normalized_validation_PAL_IMPL_AUDIT_VALIDATE/`).  
- **Interpretation:** registry/strategy-map hygiene only — **still unsafe as “PAL-vs-external paired scale-up” justification**.

### Larger paired PAL API run

**BLOCKED** until the PAL executor + controller + surfacing/port plan is landed and PAL tests pass.
