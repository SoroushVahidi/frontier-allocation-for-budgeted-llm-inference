# Real-model fixed-budget pilot note

- Run id: `20260417T000501Z`
- Providers: openai
- Datasets: Idavidrein/gpqa
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | Idavidrein/gpqa | adaptive_relative_rank: acc=0.050, avg_actions=1.40, budget_exhaustion=0.00, avg_calibrated_z=-0.204259
- openai | Idavidrein/gpqa | adaptive_score_plus_progress: acc=0.033, avg_actions=1.25, budget_exhaustion=0.00, avg_calibrated_z=-0.248668
- openai | Idavidrein/gpqa | adaptive_learned_branch_score_v4: acc=0.017, avg_actions=1.35, budget_exhaustion=0.00, avg_calibrated_z=-0.212765
- openai | Idavidrein/gpqa | best_of_n: acc=0.167, avg_actions=7.77, budget_exhaustion=0.87, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.067

## Calibration stats (provider-specific mean/std)
- openai: mean=0.3619, std=0.2277, n_score_samples=400

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | Idavidrein/gpqa: raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
