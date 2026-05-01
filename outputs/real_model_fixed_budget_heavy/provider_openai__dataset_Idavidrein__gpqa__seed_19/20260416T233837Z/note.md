# Real-model fixed-budget pilot note

- Run id: `20260416T233837Z`
- Providers: openai
- Datasets: Idavidrein/gpqa
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | Idavidrein/gpqa | adaptive_relative_rank: acc=0.050, avg_actions=1.50, budget_exhaustion=0.02, avg_calibrated_z=-0.274114
- openai | Idavidrein/gpqa | adaptive_score_plus_progress: acc=0.017, avg_actions=1.38, budget_exhaustion=0.03, avg_calibrated_z=-0.306168
- openai | Idavidrein/gpqa | adaptive_learned_branch_score_v4: acc=0.050, avg_actions=1.47, budget_exhaustion=0.02, avg_calibrated_z=-0.293711
- openai | Idavidrein/gpqa | best_of_n: acc=0.133, avg_actions=7.63, budget_exhaustion=0.80, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.062

## Calibration stats (provider-specific mean/std)
- openai: mean=0.3883, std=0.2358, n_score_samples=421

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | Idavidrein/gpqa: raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
