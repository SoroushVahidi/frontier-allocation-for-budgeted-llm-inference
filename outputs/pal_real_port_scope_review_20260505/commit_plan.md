# Recommended commit plan (no staging/commits performed in this review)

## Option A — Single squashed PR (fastest review if team accepts breadth)

Include **all** source/test files below; exclude **all** `outputs/**` except optionally a short doc note in-repo (not required).

**Files (tracked + intended new source/tests):**

- `experiments/pal_executor.py` *(add)*
- `experiments/branching.py`
- `experiments/controllers.py`
- `experiments/output_layer_repair.py`
- `experiments/frontier_matrix_core.py`
- `experiments/strategy_seeded_semantic_diversity_frontier_v1.py`
- `scripts/run_cohere_real_model_cost_normalized_validation.py`
- `scripts/materialize_pal_smoke_summary.py` *(add)*
- `tests/test_pal_executor.py` *(add)*
- `tests/test_pal_variant.py` *(add)*
- `tests/test_pal_smoke_postprocess.py` *(add)*
- `tests/test_method_validation_pal_tiebreak_registry.py` *(add)*
- `tests/test_output_layer_frontier_surfacing.py` *(add)*
- `tests/test_guarded_k1_frontier4_method.py` *(add)*

## Option B — Two-commit PR (clearer changelog)

1. **`feat(pal): executor, parsing, output-layer, registry, runner`**
   - `pal_executor.py`, `branching.py`, `output_layer_repair.py`, `frontier_matrix_core.py`, `strategy_*.py`, `run_cohere_*.py`, `materialize_pal_smoke_summary.py`, PAL-focused tests (`test_pal_*`, `test_method_validation_*`, surfacing).

2. **`feat(controller): optional decomp/opcheck seeds + PAL wiring in DR frontier gate`**
   - `controllers.py` only — isolates the largest behavioral surface for bisect/revert.

*Trade-off:* second commit alone is nonsensical without the first — order matters.

## Option C — Split opcheck/decomp_eq registry (usually **not** worth it here)

Possible only if tests are rewritten to drop `METHOD_*_OPCHECK` imports and matrix specs. Current `test_pal_variant.py` asserts opcheck/unit_track metadata contracts — **those specs/constants should stay paired with this PR** unless tests move to a smoke suite branch.

## Pre-commit guardrails

1. Confirm `git status` shows **no** staged `outputs/`, caches, logs, `.env`, keys.
2. Re-run offline pytest subset or full suite per CI.
3. Optional: `python -m compileall experiments scripts` using the same interpreter as CI.
