# Stage-3 Integrated vs External Replay Checkpoint (Dry Run)

- Method alias: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1_validated_fixes`
- Cases selected: 50
- Planned integrated calls: 50
- Cap: 50
- Planned calls within cap: True
- External outputs reused: True
- Baselines: external_l1_max, external_tale, external_s1, best_external

## Execution mode
- no_api_calls=true (dry-run provenance only).
- live_execution_supported=False

## Notes
- This runner validates replay-ready schema and call-plan only.
- It intentionally does not execute model calls in this revision.
