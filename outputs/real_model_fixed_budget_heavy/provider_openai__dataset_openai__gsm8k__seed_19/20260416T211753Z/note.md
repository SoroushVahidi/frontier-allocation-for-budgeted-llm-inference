# Real-model fixed-budget pilot note

- Run id: `20260416T211753Z`
- Providers: openai
- Datasets: openai/gsm8k
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | openai/gsm8k | adaptive_relative_rank: acc=0.017, avg_actions=1.13, budget_exhaustion=0.00, avg_calibrated_z=-0.193321
- openai | openai/gsm8k | adaptive_score_plus_progress: acc=0.017, avg_actions=1.13, budget_exhaustion=0.00, avg_calibrated_z=-0.193412
- openai | openai/gsm8k | adaptive_learned_branch_score_v4: acc=0.017, avg_actions=1.13, budget_exhaustion=0.00, avg_calibrated_z=-0.193347
- openai | openai/gsm8k | best_of_n: acc=0.983, avg_actions=8.00, budget_exhaustion=1.00, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.258

## Calibration stats (provider-specific mean/std)
- openai: mean=0.2925, std=0.1500, n_score_samples=381

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | openai/gsm8k: raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
