# Cohere direct-reserve artifact recovery audit

## Scope
Searched for prior Cohere direct-reserve validation artifacts and related coverage/scorer/trace packages before any regeneration.

## Search results
- Original expected package present: **no** (`outputs/cohere_direct_reserve_validation_20260426T_COHERE_DIRECT_RESERVE_CONFIRM`).
- Related requested pattern directories in checkout: only regenerated package was found after recovery run.
- Machine-readable inventory: `outputs/cohere_direct_reserve_artifact_recovery_audit/artifact_inventory.csv`.

## Decision
No suitable prior package with required files was available in the checkout. Reconstruction from docs alone was insufficient for per-case replay IDs. A constrained regeneration was run with Cohere real API under the requested minimal settings.

## Regenerated source package
- `outputs/cohere_direct_reserve_validation_REGENERATED_FOR_REPLAY_20260426T120000Z`

## Stable replay seed package
- Created: `outputs/cohere_direct_reserve_failure_replay_seed_latest/`
- Replay cases: **5**
- Loss cases: **5**
- Difference cases: **5**
- Control degradations: **1**
- Full traces included: **yes** (`action_trace.jsonl`, `final_branch_states.jsonl`, `tree_decision_traces.jsonl`)
- Missing fields listed: none reported

## Notes on portability and size
Trace files were copied into the seed package because each file is below 1 MB in this run.
