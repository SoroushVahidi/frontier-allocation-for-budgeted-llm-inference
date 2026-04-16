# when_solve_when_verify status

- Generated (UTC): `2026-04-16T01:40:38.992096+00:00`
- Baseline: `when_solve_when_verify`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an adjacent import protocol, not a full in-repo reproduction.
- Imported outputs must pass strict contract validation.

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
- Validated adjacent import for fixed-budget SC-vs-GenRM comparisons.

Not safe now:
- Claiming direct in-repo reproduction or control-equivalent comparability.
