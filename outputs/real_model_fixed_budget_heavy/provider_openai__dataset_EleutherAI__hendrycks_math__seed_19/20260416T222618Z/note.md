# Real-model fixed-budget pilot note

- Run id: `20260416T222618Z`
- Providers: openai
- Datasets: EleutherAI/hendrycks_math
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | EleutherAI/hendrycks_math | adaptive_relative_rank: acc=0.133, avg_actions=2.22, budget_exhaustion=0.02, avg_calibrated_z=-0.397587
- openai | EleutherAI/hendrycks_math | adaptive_score_plus_progress: acc=0.083, avg_actions=1.77, budget_exhaustion=0.02, avg_calibrated_z=-0.511154
- openai | EleutherAI/hendrycks_math | adaptive_learned_branch_score_v4: acc=0.133, avg_actions=2.03, budget_exhaustion=0.05, avg_calibrated_z=-0.434029
- openai | EleutherAI/hendrycks_math | best_of_n: acc=0.783, avg_actions=7.88, budget_exhaustion=0.93, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.283

## Calibration stats (provider-specific mean/std)
- openai: mean=0.4952, std=0.2944, n_score_samples=512

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | EleutherAI/hendrycks_math: raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
