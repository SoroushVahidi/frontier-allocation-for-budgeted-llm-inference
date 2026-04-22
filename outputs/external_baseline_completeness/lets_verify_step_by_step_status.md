# lets_verify_step_by_step status

- Generated (UTC): `2026-04-22T02:49:23.638381+00:00`
- Baseline: `lets_verify_step_by_step`
- Status: `import_validated`
- Classification: `partial_runnable_adjacent`
- Control-equivalence: `adjacent`
- Provenance level: `official`

## Canonical integration hooks
- Contract: `configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json`.
- Validator: `scripts/verify_lets_verify_step_by_step_import.py`.
- Runner: `scripts/run_lets_verify_step_by_step_adjacent_integration.py`.

## Conservative interpretation
- This lane is partial-runnable and adjacent-only.
- It verifies public PRM800K assets and a contract-bound MATH import slice.
- It does not claim full in-repo faithful reproduction.
