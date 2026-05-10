# PAL real implementation port — validation report

Workspace: ``. No Cohere/HF/OpenAI calls were made for this report beyond offline dataset access already satisfied by the test suite; `--validate-methods-only` was run in the same offline environment.

## Files changed

**Modified (tracked):**

- `experiments/branching.py` — PAL JSON fields on expand trace (`pal_code`, `pal_json_answer`, `pal_confidence`).
- `experiments/controllers.py` — PAL branch flags, prompt/seed path, `execute_pal_code` integration, overlay metadata, candidate-pool wiring (large diff vs prior clean branch).
- `experiments/frontier_matrix_core.py` — `_pal` strategy kwargs (`enable_pal_branch=True`, `pal_budget_actions=1`, selection policy); restored **decomp-eq** and **op-check** matrix entries/constants imports for parity with tests.
- `experiments/output_layer_repair.py` — PAL-aware selector pool augmentation, overlay promotion helpers, residual integration hook as wired from source tree.
- `experiments/strategy_seeded_semantic_diversity_frontier_v1.py` — method ID constants including `…_tiebreak_opcheck` and `…_tiebreak_decomp_eq`.
- `scripts/run_cohere_real_model_cost_normalized_validation.py` — METHODS registry rows and optional PAL residual-integration path aligned with ported implementation.

**Added (untracked in this workspace clone):**

- `experiments/pal_executor.py` — restricted AST executor, `execute_pal_code`, numeric extraction, sanitized errors.
- `scripts/materialize_pal_smoke_summary.py` — postprocessing prefers `result_metadata` with fallback.
- Tests: `tests/test_pal_executor.py`, `tests/test_pal_variant.py`, `tests/test_pal_smoke_postprocess.py`, `tests/test_method_validation_pal_tiebreak_registry.py`, `tests/test_output_layer_frontier_surfacing.py`, `tests/test_guarded_k1_frontier4_method.py` (last copied from primary checkout because it was absent here).

Artifact-only: this directory under `outputs/pal_real_port_validation_20260505/` (`port_summary.json`, CSV/JSON checks, `test_report.md`, `report.md`).

## True PAL executor in clean branch

**Yes.** `experiments/pal_executor.py` is present and `execute_pal_code` is importable and exercised by `tests/test_pal_executor.py`.

## `_pal` spec: `enable_pal_branch=True`

**Yes.** `build_frontier_strategies(...)` returns the PAL method controller with `enable_pal_branch` True and `pal_budget_actions` ≥ 1 (observed value `1`). See `pal_symbol_check.csv` / audit JSON.

## Controller PAL execution path reachable in tests

**Yes.** `tests/test_pal_variant.py` runs the PAL controller on pilot examples and asserts `pal_execution` metadata; subprocess test loads the runner module and validates methods-only.

## PAL candidate in selector pool / final_nodes

**Yes (where budget spent).** Tests assert pool entries with `source_family=="pal_seed"` when `pal_budget_cost_observed` &gt; 0, and overlay tests cover weak-frontier promotion. Output-layer / frontier surfacing coverage is exercised by `tests/test_output_layer_frontier_surfacing.py` (passed).

## PAL-aware gold_in_tree / Discovery3

**Partial / indirect.** The ported output-layer path includes PAL-aware augmentation and residual integration hooks; **`tests/test_output_layer_frontier_surfacing.py` passed**, which encodes downstream surfacing/accounting expectations. There is **no standalone “Discovery3” unit test name** in the required list; deeper gold-in-tree edge cases may still need dedicated cases if you want exhaustive coverage.

## Tests passed / failed

**All required tests passed:** 82 total in the single combined run (see `test_report.md`).

## validate-methods-only

**Succeeded:** exit code 0, `validated_rows=2 bad_rows=0`. Report CSV path recorded in `port_summary.json`.

## Larger paired PAL API run unblocked

**Conditionally yes.** Registry resolution and controller wiring are validated offline; a **live** paired run still requires provider credentials, spend controls, and non-`--validate-methods-only` execution — intentionally **not** run here.

## Remaining caveats

1. **Scope:** `experiments/controllers.py` diff is very large relative to a “PAL-only” port; review before merge to ensure no unintended behavior drift vs the pre-merge clean branch.
2. **Decomp-eq / op-check / unit-track:** Reintroduced in the strategy constant + `frontier_matrix_core` matrix because **tests require** `opcheck`/`unit_track` metadata contracts; this matches the primary checkout’s matrix layout.
3. **Side-effect outputs:** Running the validator created timestamped directories under `outputs/cohere_real_model_cost_normalized_validation_*` — **do not stage** per project rules unless you explicitly want them.
4. **Venv:** This worktree has no `.venv`; tests used the sibling repo’s virtualenv with `cwd` set to `research-next-wt` — replicate that or install deps into a local venv before CI.
5. **No live API smoke** was executed after porting (per instructions).
