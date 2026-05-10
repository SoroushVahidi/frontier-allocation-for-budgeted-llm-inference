# Integrated structural_commit_v1 + targeted_retry_v1 offline replay

- Method scaffold: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1`
- No API calls were made; this is offline provenance stitching over existing artifacts.

## Estimated fixes from existing evidence
- Estimated fixed: 25 / 71
- structural component: 7
- targeted component (tested): 18

## Remaining gaps
- Estimated not fixed or not covered: 46 / 71
- untested_targeted_retry_cases: 11
- unknown_mechanism_cases: 12
- cases_outside_allowlist_or_supported_scaffolds: 23
- cases_with_no_replay_or_insufficient_provenance: 0

## Recommendation
This does not justify a broad checkpoint versus external_l1_max yet. Next step: (A) run a capped live integrated pilot on covered/allowlisted cases, or (B) wait for full live integration then perform a clean checkpoint comparison.