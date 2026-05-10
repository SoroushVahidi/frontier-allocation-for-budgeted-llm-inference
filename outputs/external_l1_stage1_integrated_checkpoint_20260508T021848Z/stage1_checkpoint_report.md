# Stage-1 integrated checkpoint vs external_l1_max

- Case set: `/home/soroush/research-next-wt/outputs/external_l1_checkpoint_readiness_20260508T021402Z/recommended_checkpoint_cases.csv`
- Calls used: 0 / 5
- External baseline reused; external_l1 was not regenerated.

## External sources reused
- `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/external_l1_results.csv`
- `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/external_l1_results.csv`
- `/home/soroush/research-next-wt/outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_results.jsonl`

## Scoreboard
- external_l1_correct: 34/40
- baseline_pal_correct: 33/40
- integrated_correct: 33/40
- integrated_minus_external_l1: -1
- integrated_minus_baseline_pal: 0
- paired_integrated_only: 1
- paired_external_l1_only: 2

## Recommendation
Stage-2 100-case checkpoint is justified if API/parsing remains stable (this run: no API/parsing failures).

## Caveats
- This slice contains only targeted-retry live deltas and base-method carryover; structural-commit was not exercised.
- Gold labels were used only for offline scoring.