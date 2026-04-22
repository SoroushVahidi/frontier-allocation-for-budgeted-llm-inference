# tree_plv status

- Generated (UTC): `2026-04-22T03:10:07.274644+00:00`
- Baseline: `tree_plv`
- Status: `import_validated`
- Classification: `partial_runnable_adjacent`
- Control-equivalence: `adjacent`
- Provenance level: `official_paper_and_paper_cited_repo`

## Canonical integration hooks
- Contract: `configs/tree_plv_adjacent_comparison_contract_v1.json`.
- Validator: `scripts/verify_tree_plv_import.py`.
- Runner: `scripts/run_tree_plv_adjacent_integration.py`.

## Conservative interpretation
- This lane is partial-runnable and adjacent-only.
- It validates paper↔repo provenance and a contract-bound benchmark import slice.
- It does not claim full faithful in-repo reproduction.
