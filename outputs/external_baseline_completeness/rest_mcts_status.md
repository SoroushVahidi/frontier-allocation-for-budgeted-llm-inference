# rest_mcts status

- Generated (UTC): `2026-04-22T12:00:00+00:00`
- Baseline: `rest_mcts`
- Status (v1): `import_validated`
- Lane strength: `partial_runnable_adjacent`
- Integration kind: `official_adjacent_contract_lane`

## Conservative interpretation
- This is an official adjacent contract lane, not full in-repo reproduction.
- Imported outputs must pass strict validator checks under an explicit contract.

## Canonical contract lane
- Contract: `configs/rest_mcts_adjacent_comparison_contract_v2.json`
- Runner: `scripts/run_rest_mcts_adjacent_integration.py`
- Validator: `scripts/verify_rest_mcts_import.py`
- Output family: `outputs/rest_mcts_adjacent_integration/<run_id>/`

## Safe vs unsafe claims
Safe now:
- Artifact-backed adjacent integration with machine-readable outputs.

Not safe now:
- Claiming full faithful in-repo reproduction or direct control-equivalent comparability.
