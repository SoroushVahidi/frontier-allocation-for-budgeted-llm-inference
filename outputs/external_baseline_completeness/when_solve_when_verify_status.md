# when_solve_when_verify status

- Generated (UTC): `2026-04-21T19:09:41.789427+00:00`
- Baseline: `when_solve_when_verify`
- Status: `import_validated`
- Control-equivalence: `adjacent`
- Provenance level: `official`
- Integration kind: `official_adjacent_import_validated`

## Conservative interpretation
- This is an official import-validation lane, not a full in-repo reproduction.
- Imported outputs must pass strict contract validation with verdict `import_validated`.

## Canonical integration hooks
- Config: `configs/when_solve_when_verify_official_import_v1.json`.
- Validator: `scripts/verify_when_solve_when_verify_import.py`.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - solution_generation
  - verification_generation
  - fixed_budget_evaluation
- Strategy coverage must include `self_consistency` and at least one `genrm_*` strategy.
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Official adjacent import-validated reporting for fixed-budget solve-vs-verify comparisons.

Not safe now:
- Claiming direct frontier-allocation comparability or full in-repo paper reproduction.
