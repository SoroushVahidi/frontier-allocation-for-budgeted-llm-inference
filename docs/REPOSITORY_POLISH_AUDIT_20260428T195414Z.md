# Repository polish audit (reviewer repro consistency pass)

Date: 2026-04-28 (UTC)

## What changed

- Updated reviewer-facing reproduction commands to avoid implying full-suite green in all environments:
  - `README.md`
  - `QUICKSTART.md`
  - `docs/REVIEWER_REPRO_AND_SCOPE_GUIDE.md`
- Added explicit stable reviewer-safe pytest subset wiring:
  - `Makefile` (`reviewer-test` target; `check` now uses reviewer-safe subset)
- Enabled TALE external baseline in real-model cost validator strategy construction:
  - `scripts/run_cohere_real_model_cost_normalized_validation.py`
- Added postprocessing helper for reviewer-facing output files:
  - `scripts/build_real_model_cost_validation_outputs.py`

## Reviewer-safe tests

Use:

```bash
python scripts/check_repo_health.py
python -m pytest -q tests/test_frontier_router.py tests/test_repository_structure.py tests/test_check_repo_health_paths.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Observed outcomes in this pass:
- `check_repo_health.py`: pass
- reviewer-safe subset: pass (`10 passed`)
- canonical artifact runner: pass

## Optional / environment-dependent tests

- Full suite command:

```bash
python -m pytest -q
```

- This remains optional for reviewer baseline reproduction because some tests depend on:
  - generated artifact compatibility (e.g., serialized model/toolchain versions),
  - optional datasets/features and environment-specific runtime support.

## Canonical artifact runner status

- `python scripts/paper/run_all_neurips_paper_artifacts.py` completed successfully in this pass.

## Claim-scope discipline

- No claim boundaries were changed.
- `strict_f3` (manuscript matched-surface representative) vs `strict_gate1_cap_k6` (broader operational default) distinction remains explicit.
- Real-model/cost-aware runs remain supporting/diagnostic unless explicitly promoted by canonical decision docs.
