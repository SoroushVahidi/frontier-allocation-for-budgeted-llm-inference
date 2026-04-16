# cascade_routing status

- Generated (UTC): `2026-04-16T01:51:52.361139+00:00`
- Baseline: `cascade_routing`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an adjacent import protocol, not full in-repo reproduction.
- Imported outputs must pass strict contract validation.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - query_generation_or_data_download
  - dataset_preprocessing
  - routing_and_cascading_experiment_execution
  - postprocess_result_aggregation
- Strategy coverage must include `routing`, `cascading`, and `cascade_routing`.
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Validated adjacent import for cascade-routing outputs.

Not safe now:
- Claiming direct in-repo reproduction or control-equivalent comparability.
