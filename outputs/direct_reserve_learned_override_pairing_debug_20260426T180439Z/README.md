# direct_reserve learned-override pairing debug

- validation input: `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z`
- compared methods: `direct_reserve_strong_plus_diverse_v1` vs `direct_reserve_strong_plus_diverse_learned_override_v1`
- This is an offline artifact-only diagnosis; no API calls were made.
- `fallback_mismatch_cases.csv` flags cases where learned override did not trigger but final answer still differed from base.
- `candidate_pool_diff.csv` flags cases where candidate sets differ across methods (unpaired/stochastic generation risk).
