# openr status

- Generated (UTC): `2026-04-16T02:26:43.091749+00:00`
- Baseline: `openr`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an adjacent import protocol, not full in-repo reproduction.
- Imported outputs must pass strict contract validation.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - lm_rm_service_startup
  - inference_evaluation_run
  - result_artifact_export
- Strategy coverage must include `cot` and at least one tree-search method (`beam_search`, `vanila_mcts`, or `rstar_mcts`).
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Validated adjacent import for OpenR outputs.

Not safe now:
- Claiming direct in-repo reproduction or control-equivalent comparability.
