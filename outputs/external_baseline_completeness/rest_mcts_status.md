# rest_mcts status

- Generated (UTC): `2026-04-16T02:17:13.689937+00:00`
- Baseline: `rest_mcts`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an adjacent import protocol, not full in-repo reproduction.
- Imported outputs must pass strict contract validation.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - value_model_bootstrap_or_training
  - mcts_trace_generation
  - policy_self_training
  - benchmark_evaluation
- Results must include `mcts` search rows with explicit search settings and metrics.
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Validated adjacent import for ReST-MCTS outputs.

Not safe now:
- Claiming direct in-repo reproduction or control-equivalent comparability.
