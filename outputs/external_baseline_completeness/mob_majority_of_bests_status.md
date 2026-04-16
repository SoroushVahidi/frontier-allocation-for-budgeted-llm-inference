# mob_majority_of_bests status

- Generated (UTC): `2026-04-16T02:06:45.859747+00:00`
- Baseline: `mob_majority_of_bests`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an adjacent import protocol, not full in-repo reproduction.
- Imported outputs must pass strict contract validation.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - dataset_loading_from_jsonl_gz
  - algorithm_evaluation_via_main_py
  - aggregated_csv_export
- Algorithm coverage must include `bon` and at least one `mob_*` variant.
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Validated adjacent import for MoB outputs.

Not safe now:
- Claiming direct in-repo reproduction or control-equivalent comparability.
