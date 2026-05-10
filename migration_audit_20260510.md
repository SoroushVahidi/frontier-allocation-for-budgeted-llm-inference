# Migration Audit Report - 2026-05-10

## Candidate Outside Folders Inspected
- `~/diverse-root-clean`
- `~/pal-pilot-clean`
- `~/outputs`
- `~/scripts`
- `~/tests`
- `~/migration_artifacts_20260509`
- `~/research-next-wt`

## Files/Directories that look project-related

### `~/research-next-wt` (High Priority)
- `experiments/`: Several unique scripts (e.g., `adaptive_retry_router.py`, `call_accounting.py`, `target_staged_pal_pilot_runner.py`).
- `outputs/`: Many unique experiment result folders.
- `docs/`: Many unique report files (e.g., `COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_*.md`).
- `local_patches/`: Contains `selector_isolated_exploration_log_failed_variant_20260507T042513Z.patch`.
- `prompts/`: Contains `target_staged_pal_retry/`.
- `preserved_artifacts/`: Contains a copy of `migration_artifacts_20260509`.

### `~/outputs`
- `provider_readiness_20260502T184233Z/`: Contains readiness report and summary.

### `~/scripts`
- `check_provider_readiness.py`: A version of the provider check script (conflicts with canonical).

### `~/tests`
- `run_tests.py`: Unique test runner script.
- `test_check_provider_readiness.py`: Test for the provider check script (conflicts with canonical).

### `~/migration_artifacts_20260509`
- Various `.tgz` and `.txt` files from a previous migration effort.

## Files already present in the canonical repo
- Most files in `~/diverse-root-clean` and `~/pal-pilot-clean` are identical to `~/frontier-allocation-for-budgeted-llm-inference`.
- `scripts/check_provider_readiness.py` exists in canonical but the home-level version is different.
- `tests/test_check_provider_readiness.py` exists in canonical but the home-level version is different.

## Unique files needing migration
- All unique scripts in `~/research-next-wt/experiments/`.
- All unique output folders in `~/research-next-wt/outputs/`.
- All unique docs in `~/research-next-wt/docs/`.
- `~/research-next-wt/local_patches/`
- `~/research-next-wt/prompts/`
- `~/outputs/provider_readiness_20260502T184233Z/`
- `~/tests/run_tests.py`
- `~/migration_artifacts_20260509/` (to be archived)

## Suspected unrelated files
- `.aider.chat.history.md`, `.aider.input.history`, `.aider.tags.cache.v4` in `~/research-next-wt` (Aider metadata).
- `.ruff_cache`, `.pytest_cache`, `__pycache__` in various directories.

## Suspected secrets or files that should not be committed
- `api_key_readiness.json` and various `token_cost_latency_summary.csv` files were found. These appear to be reports and not the keys themselves, but they should be handled with care and not committed to Git if they contain sensitive info.
- No `.env` files were found in the top 3 levels of the candidate directories.

## Recommended Move Plan
1.  **Unique Experiments/Docs/Outputs**: Move from `~/research-next-wt` to canonical.
2.  **Unique Folders**: Move `local_patches/` and `prompts/` from `~/research-next-wt` to canonical.
3.  **Home-level Outputs**: Move `~/outputs/provider_readiness_*` to `~/frontier-allocation-for-budgeted-llm-inference/outputs/`.
4.  **Home-level Scripts/Tests**: Move `~/scripts/` and `~/tests/` files to `~/frontier-allocation-for-budgeted-llm-inference/_migration_review/` to avoid overwriting canonical versions.
5.  **Archives**: Move `~/migration_artifacts_20260509` to `~/frontier-allocation-for-budgeted-llm-inference/archive/`.
6.  **Cleanup**: After verification, `~/diverse-root-clean`, `~/pal-pilot-clean`, and `~/research-next-wt` can be removed.
