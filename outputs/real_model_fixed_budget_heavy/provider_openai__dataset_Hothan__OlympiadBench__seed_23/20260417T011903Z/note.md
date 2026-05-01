# Real-model fixed-budget pilot note

- Run id: `20260417T011903Z`
- Providers: openai
- Datasets: Hothan/OlympiadBench
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | Hothan/OlympiadBench | adaptive_relative_rank: acc=0.017, avg_actions=1.15, budget_exhaustion=0.00, avg_calibrated_z=-0.249404
- openai | Hothan/OlympiadBench | adaptive_score_plus_progress: acc=0.033, avg_actions=1.23, budget_exhaustion=0.00, avg_calibrated_z=-0.212235
- openai | Hothan/OlympiadBench | adaptive_learned_branch_score_v4: acc=0.017, avg_actions=1.22, budget_exhaustion=0.00, avg_calibrated_z=-0.228696
- openai | Hothan/OlympiadBench | best_of_n: acc=0.383, avg_actions=8.00, budget_exhaustion=1.00, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.113

## Calibration stats (provider-specific mean/std)
- openai: mean=0.3059, std=0.1689, n_score_samples=393

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | Hothan/OlympiadBench: raw_top=best_of_n, calibrated_top=adaptive_score_plus_progress, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
